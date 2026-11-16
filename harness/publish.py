"""Package a run for the public results repository and publish it.

`package` builds the product in a fresh container, checks that the build is self-contained on a
bare system, and writes report, source zip and artefact metadata into the results repository.
`publish` commits and pushes that repository and uploads executables as GitHub Release assets.
Only derived, non-sensitive data leaves the run folder: no raw logs, no container home, and
hidden-test results only as category totals.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import tarfile
import tempfile

from . import core

CONTRACT_SMOKE_CONFIG = {'seed': 1, 'world': {'width': 16, 'height': 16},
                         'initial': {'plants': 40, 'herbivores': 10, 'carnivores': 2}}
BARE_IMAGE = 'docker.io/library/ubuntu:24.04'
SECRET_MIN_LENGTH = 20


def results_dir(cfg):
    path = (cfg.get('results') or {}).get('path')
    if not path:
        raise RuntimeError('No results repository configured ("results.path" in benchmark.json)')
    p = pathlib.Path(path).expanduser()
    p = (p if p.is_absolute() else core.ROOT / p).resolve()
    if not (p / '.git').exists():
        raise RuntimeError(f'Results repository not found at {p}; clone or `git init` it first')
    return p


def slug(run):
    return f'{run.name}-{run.track}-{run.run_id}'


def github_url(repo):
    """https URL of a repository's origin, or None."""
    try:
        url = core.git(repo, 'remote', 'get-url', 'origin')
    except RuntimeError:
        return None
    if url.startswith('git@github.com:'):
        url = 'https://github.com/' + url[len('git@github.com:'):]
    return url[:-4] if url.endswith('.git') else url


# --- secret scan ---------------------------------------------------------------

def login_secrets(run):
    """Every long string stored in the run's copied login files."""
    found = set()
    def walk(v):
        if isinstance(v, dict):
            for x in v.values(): walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
        elif isinstance(v, str) and len(v) >= SECRET_MIN_LENGTH:
            found.add(v)
    for rel in core.LOGIN_FILES[run.cli]:
        f = run.home / rel
        if not f.is_file():
            continue
        text = f.read_text(encoding='utf-8', errors='replace')
        try:
            walk(json.loads(text))
        except ValueError:
            pass   # commented config files (jsonc) hold no login tokens we can parse
    return found


def leaked_secrets(tree, secrets):
    """Files under `tree` containing one of the secrets. An agent can read its own login,
    so the product source is checked before anything is published."""
    hits = []
    needles = [s.encode() for s in secrets]
    if not needles:
        return hits
    for f in sorted(pathlib.Path(tree).rglob('*')):
        if f.is_file() and not f.is_symlink():
            data = f.read_bytes()
            if any(n in data for n in needles):
                hits.append(str(f.relative_to(tree)))
    return hits


# --- build and self-containment --------------------------------------------------

def build_product(cfg, product, log):
    """Run ./setup.sh and ./build.sh in a fresh benchmark container. True on success."""
    argv = [core.runtime(cfg), 'run', '--rm', '--network', 'pasta:--map-guest-addr,none',
            '-v', f'{product}:{core.CONTAINER_WS}', cfg['container']['image'],
            'bash', '-c', f'cd {core.CONTAINER_WS} && ./setup.sh && ./build.sh']
    r = core.cmd(argv, product, cfg['eval']['timeout_seconds'], logfile=log)
    return r['exit_code'] == 0 and (product / 'dist' / 'evosim').is_file()


def self_contained(cfg, dist):
    """Does dist/ work on a bare Ubuntu with no runtimes and no network? Returns (ok, detail)."""
    with tempfile.TemporaryDirectory(prefix='evo-bare-') as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / 'c.json').write_text(json.dumps(CONTRACT_SMOKE_CONFIG))
        argv = [core.runtime(cfg), 'run', '--rm', '--network', 'none', '-v', f'{dist}:/dist:ro', '-v', f'{tmp}:/t',
                BARE_IMAGE, 'bash', '-c',
                '/dist/evosim version && /dist/evosim run --config /t/c.json --ticks 50 --out /t/r.json']
        r = core.cmd(argv, tmp, 300)
        if r['exit_code'] != 0:
            return False, f'exit status {r["exit_code"]}: {r["output"].strip()[-300:]}'
        try:
            result = json.loads((tmp / 'r.json').read_text())
            if not isinstance(result.get('state_hash'), str):
                return False, 'run wrote no state_hash'
        except (OSError, ValueError):
            return False, 'run wrote no valid result JSON'
    return True, ''


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


# --- published documents -------------------------------------------------------

def public_report(run, state):
    """The run summary plus per-task and per-evaluation figures; nothing free-text from logs."""
    row = core.summarize(core.read(run.meta), state)
    tasks = {}
    for tid, t in state['tasks'].items():
        hist = t['history']
        tasks[tid] = {'status': t['status'], 'cycles': t['cycle'] if hist else 0, 'phases_attempted': len(hist),
                      'phases_failed': sum(1 for e in hist if e.get('failure_class')),
                      'agent_seconds': round(sum(e['seconds'] for e in hist), 1)}
    keep = ('label', 'commit', 'eval_version', 'passed', 'due', 'total', 'categories', 'metrics', 'done_tasks', 'timestamp')
    evaluations = [{k: e[k] for k in keep if k in e} for e in state.get('evaluations', []) if 'error' not in e]
    row['evaluation'] = evaluations[-1] if evaluations else None
    return {**row, 'tasks': tasks, 'evaluations': evaluations}


def run_readme(report, artifact, release_url, harness_url):
    ev = report['evaluation']; c = report['status_counts']
    lines = [f'# {report["profile"]} · {report["track"]} · {report["run_id"]}', '',
             f'One run of the [Evolution Agent Benchmark]({harness_url or "#"}): a coding agent builds an evolution '
             'simulation from an empty project across 27 dependent tasks, with no human help.', '',
             core.table(['', ''], [
                 ['Model', ', '.join(report['reported_models']) or report['model'] or 'CLI default'],
                 ['Agent CLI', report['cli_version'] or report['cli']],
                 ['Track', report['track']],
                 ['Started', report['created'][:10]],
                 ['State', 'finished' if report['finished'] else 'in progress'],
                 ['Tasks done', f'{c["DONE"]} of {report["tasks_total"]} ({c["BLOCKED"]} blocked)'],
                 ['Passed review in first cycle', core.fmt_pct(report['first_cycle_pass_ratio'])],
                 ['Phases attempted / failed', f'{report["phases_attempted"]} / {report["phases_failed"]}'],
                 ['Operator interventions', report['operator_interventions']],
                 ['Agent time', core.fmt_time(report['wall_seconds_agent_calls'])],
                 ['Tokens (fresh input / cached input / output)',
                  ' / '.join(core.fmt_count(report['reported_' + k]) for k in core.TOKEN_KINDS)],
                 ['Cost', core.fmt_cost(report['reported_total_cost_usd'])],
                 ['Isolation', report['isolation']]]), '']
    lines += ['## Hidden test results', '']
    if ev:
        lines += [f'Scored by a private black-box suite the agent never saw, after {ev["label"]}: '
                  f'**{ev["passed"]} of {ev["total"]} checks passed**.', '',
                  core.table(['Category', 'Passed', 'Checks'],
                             [[core.label(k), v['passed'], v['total']] for k, v in ev['categories'].items()]), '']
        if ev['metrics'].get('ticks_per_second') is not None:
            lines += [f'Measured speed: {ev["metrics"]["ticks_per_second"]} ticks per second at about 2,000 individuals.', '']
        if len(report['evaluations']) > 1:
            lines += ['### Progress over the run', '',
                      core.table(['After', 'Tasks done', 'Checks passed', 'Checks due'],
                                 [[e['label'], e.get('done_tasks', '—'), e['passed'], e['due']] for e in report['evaluations']]), '']
    else:
        lines += ['This run was not scored.', '']
    lines += ['## Download', '']
    if artifact['build_ok']:
        note = ('It is self-contained: it ran on a bare Ubuntu 24.04 with no runtimes installed.' if artifact['self_contained']
                else f'It is **not** self-contained ({artifact["self_contained_detail"] or "check failed"}); '
                     'use the source instead.')
        where = f'[release page]({release_url})' if release_url else 'release page of this repository'
        lines += [f'- Executable (Linux x86-64): `{artifact["asset"]}` on the {where}. {note}',
                  f'  SHA-256 `{artifact["sha256"]}`, {artifact["size_bytes"] / 1e6:.1f} MB.',
                  '  Unpack it, then run `./evosim version`, `./evosim ui` or `./evosim run --help`.']
    else:
        lines += ['- No executable: the product\'s `./setup.sh` / `./build.sh` did not succeed in a fresh container.']
    lines += ['- [`source.zip`](source.zip): the final project exactly as the agent left it, including its plans, '
              'reviews and handoff notes under `tasks/*/handoffs/`.',
              '- [`report.json`](report.json): all figures above in machine-readable form, plus per-task numbers.', '',
              '> The code in this folder was written by an AI agent without human review. Run it at your own risk.', '']
    return '\n'.join(lines)


def index_readme(reports, harness_url, repo_url):
    body = core.comparison_markdown(reports).split('\n', 2)[2] if reports else '\nNo runs published yet.\n'
    lines = ['# Evolution Agent Benchmark: results', '',
             f'Published runs of the [Evolution Agent Benchmark]({harness_url or "#"}). Each coding agent, cloud or local, '
             'gets the same 27 dependent tasks and has to build an evolution simulation from an empty project on its own. '
             'Quality is scored by a private black-box test suite the agents never see.', '',
             'This page is generated; do not edit it by hand.', body, '## Runs', '']
    for r in reports:
        folder = f'results/{r["profile"]}/{r["track"]}/{r["run_id"]}'
        link = f' · [executable]({repo_url}/releases/tag/{r["profile"]}-{r["track"]}-{r["run_id"]})' if repo_url and r.get('has_asset') else ''
        lines.append(f'- [{r["profile"]} · {r["track"]} · {r["run_id"]}]({folder}/README.md){link}')
    return '\n'.join(lines) + '\n'


def rebuild_index(results):
    reports = []
    for f in sorted(results.glob('results/*/*/*/report.json')):
        r = core.read(f)
        art = f.with_name('artifact.json')
        r['has_asset'] = art.exists() and core.read(art).get('build_ok', False)
        reports.append(r)
    (results / 'README.md').write_text(index_readme(reports, github_url(core.ROOT), github_url(results)), encoding='utf-8')
    core.write(results / 'comparison.json', {'generated': core.now(), 'runs': reports})
    return reports


# --- commands ----------------------------------------------------------------

def package(run):
    cfg = run.cfg; results = results_dir(cfg); state = core.read(run.state)
    name = slug(run); dest = results / 'results' / run.name / run.track / run.run_id
    work = run.base / 'package'; shutil.rmtree(work, ignore_errors=True)
    product = work / 'product'; product.mkdir(parents=True)
    print(f'PACKAGE {name}', flush=True)
    tar = subprocess.run(['git', 'archive', '--format=tar', 'HEAD'], cwd=run.workspace, capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(product)], input=tar, check=True)
    hits = leaked_secrets(product, login_secrets(run))
    if hits:
        raise RuntimeError('Refusing to publish: the workspace contains this run\'s CLI login token in '
                           + ', '.join(hits[:5]) + '. Revoke that login and inspect the run.')
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'archive', '--format=zip', '-o', str(dest / 'source.zip'), 'HEAD'], cwd=run.workspace, check=True)

    artifact = {'asset': None, 'sha256': None, 'size_bytes': None, 'build_ok': False,
                'self_contained': False, 'self_contained_detail': '', 'release_tag': name,
                'source_commit': core.git(run.workspace, 'rev-parse', 'HEAD'), 'packaged': core.now()}
    buildable = all((product / f).is_file() for f in ('setup.sh', 'build.sh'))
    print('  building in a fresh container ...' if buildable else '  no setup.sh/build.sh, skipping build', flush=True)
    if buildable and build_product(cfg, product, work / 'build.log'):
        artifact['build_ok'] = True
        artifact['self_contained'], artifact['self_contained_detail'] = self_contained(cfg, product / 'dist')
        assets = results / 'release-assets'; assets.mkdir(exist_ok=True)
        asset = assets / f'evosim-{name}-linux-x86_64.tar.gz'
        with tarfile.open(asset, 'w:gz') as t:
            t.add(product / 'dist', arcname=f'evosim-{name}')
        artifact.update(asset=asset.name, sha256=sha256(asset), size_bytes=asset.stat().st_size)
    shutil.rmtree(product, ignore_errors=True)

    report = public_report(run, state)
    core.write(dest / 'report.json', report)
    core.write(dest / 'artifact.json', artifact)
    repo_url = github_url(results)
    release_url = f'{repo_url}/releases/tag/{name}' if repo_url else None
    (dest / 'README.md').write_text(run_readme(report, artifact, release_url, github_url(core.ROOT)), encoding='utf-8')
    gi = results / '.gitignore'
    if not gi.exists():
        gi.write_text('# Executables are published as GitHub Release assets, not committed.\nrelease-assets/\n')
    rebuild_index(results)
    print(f'  build: {"ok" if artifact["build_ok"] else "FAILED"}; self-contained: '
          f'{"yes" if artifact["self_contained"] else "no"} {artifact["self_contained_detail"]}'.rstrip())
    print(f'  written to {dest}')
    print('  review the results repository, then run: python3 run.py publish')
    return artifact


def publish(cfg, dry_run=False):
    """Commit and push the results repository; upload executables that are not released yet."""
    results = results_dir(cfg); rebuild_index(results)
    def step(argv, check=True):
        print(('DRY RUN ' if dry_run else '$ ') + ' '.join(argv), flush=True)
        if dry_run:
            return 0
        return subprocess.run(argv, cwd=results, check=check).returncode
    step(['git', 'add', '-A'])
    if dry_run or core.git(results, 'status', '--porcelain'):
        step(['git', 'commit', '-m', 'Update published benchmark results'])
    step(['git', 'push', 'origin', 'HEAD'])
    pending = []
    for f in sorted(results.glob('results/*/*/*/artifact.json')):
        a = core.read(f)
        if a.get('build_ok') and a.get('asset') and (results / 'release-assets' / a['asset']).is_file():
            pending.append(a)
    if pending and not shutil.which('gh'):
        print('GitHub CLI `gh` is not installed, so executables were not uploaded. Install it '
              '(https://cli.github.com), run `gh auth login`, then run publish again; or upload these by hand:')
        for a in pending:
            print(f'  release tag {a["release_tag"]}: release-assets/{a["asset"]}')
        return
    for a in pending:
        asset = str(results / 'release-assets' / a['asset'])
        exists = not dry_run and subprocess.run(['gh', 'release', 'view', a['release_tag']], cwd=results, capture_output=True).returncode == 0
        if exists:
            step(['gh', 'release', 'upload', a['release_tag'], asset, '--clobber'])
        else:
            step(['gh', 'release', 'create', a['release_tag'], asset, '--title', a['release_tag'],
                  '--notes', f'Executable built from an AI-agent benchmark run. SHA-256: {a["sha256"]}. Not human-reviewed; run at your own risk.'])
