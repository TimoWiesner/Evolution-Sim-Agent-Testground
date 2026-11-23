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
import re
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

SCREENSHOT_SECONDS = 180          # the contract allows the product 120 s
MAX_SCREENSHOTS = 6               # main.png plus five more, as in the contract
MAX_SCREENSHOT_BYTES = 8 << 20


def build_product(cfg, product, log, shots):
    """Run ./setup.sh and ./build.sh in a fresh benchmark container, then let the product write
    its screenshots into `shots`. True if the build succeeded; screenshots are optional."""
    script = (f'cd {core.CONTAINER_WS} && ./setup.sh && ./build.sh; rc=$?; '
              f'if [ $rc -eq 0 ]; then timeout {SCREENSHOT_SECONDS} xvfb-run -a -s "-screen 0 1920x1080x24" '
              './evosim ui --screenshots /shots; echo "screenshots exit status: $?"; fi; exit $rc')
    argv = [core.runtime(cfg), 'run', '--rm', '--network', 'pasta:--map-guest-addr,none',
            '-v', f'{product}:{core.CONTAINER_WS}', '-v', f'{shots}:/shots', cfg['container']['image'],
            'bash', '-c', script]
    r = core.cmd(argv, product, cfg['eval']['timeout_seconds'] + SCREENSHOT_SECONDS, logfile=log)
    return r['exit_code'] == 0 and (product / 'dist' / 'evosim').is_file()


def collect_screenshots(shots, dest):
    """Copy the product's PNG files into `dest` (main.png first) and return their names.
    Only real PNG files of a sane size are taken; names are reduced to safe characters."""
    shutil.rmtree(dest, ignore_errors=True)
    files = sorted((f for f in pathlib.Path(shots).glob('*.png') if f.is_file() and not f.is_symlink()),
                   key=lambda f: (f.name != 'main.png', f.name))
    names = []
    for f in files:
        name = re.sub(r'[^a-z0-9._-]', '-', f.name.lower())
        if len(names) >= MAX_SCREENSHOTS or name in names or not 0 < f.stat().st_size <= MAX_SCREENSHOT_BYTES:
            continue
        with open(f, 'rb') as h:
            if h.read(8) != b'\x89PNG\r\n\x1a\n':
                continue
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dest / name); names.append(name)
    return names


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
    keep = ('label', 'commit', 'eval_version', 'passed', 'due', 'total', 'categories', 'metrics', 'balance', 'done_tasks', 'timestamp')
    evaluations = [{k: e[k] for k in keep if k in e} for e in state.get('evaluations', []) if 'error' not in e]
    row['evaluation'] = evaluations[-1] if evaluations else None
    return {**row, 'tasks': tasks, 'evaluations': evaluations}


def run_readme(report, artifact, release_url, harness_url):
    ev = report['evaluation']; c = report['status_counts']
    lines = [f'# {report["profile"]} · {report["track"]} · {report["run_id"]}', '',
             f'One run of the [Evolution Agent Benchmark]({harness_url or "#"}): a coding agent builds an evolution '
             'simulation from an empty project across 28 dependent tasks, with no human help.', '',
             core.table(['', ''], [
                 ['Model', ', '.join(report['reported_models']) or report['model'] or 'CLI default'],
                 ['Agent CLI', report['cli_version'] or report['cli']],
                 ['Track', report['track']],
                 ['Benchmark version', report['benchmark_version']],
                 ['Started', report['created'][:10]],
                 ['State', 'finished' if report['finished'] else 'in progress'],
                 ['Tasks done', f'{c["DONE"]} of {report["tasks_total"]} ({core.fmt_blocked(report)} blocked)'],
                 ['Passed review in first cycle', core.fmt_pct(report['first_cycle_pass_ratio'])],
                 ['Phases attempted / failed', f'{report["phases_attempted"]} / {report["phases_failed"]}'],
                 ['Operator interventions', report['operator_interventions']],
                 ['Agent time', core.fmt_time(report['wall_seconds_agent_calls'])],
                 ['Tokens (fresh input / cached input / output)',
                  core.at_least(' / '.join(core.fmt_count(report['reported_' + k]) for k in core.TOKEN_KINDS), report.get('phases_without_tokens'))],
                 ['Cost', core.at_least(core.fmt_cost(report['reported_total_cost_usd']), report.get('phases_without_cost'))],
                 ['Isolation', report['isolation']]]), '']
    if report['track'] == 'subagents':
        lines += ['## Delegation', '',
                  'In this track the agent was allowed, but not required, to hand work to its CLI\'s own subagents.', '',
                  core.table(['', ''], [
                      ['Agent calls that delegated work', f'{report["phases_delegated"]} of {report["phases_attempted"]}'],
                      ['Subagents started', core.fmt_count(report['subagents_started'])]]), '']
    if report['track'] == 'parallel':
        lines += ['## Parallel work', '',
                  f'Up to {report["workers"]} agents worked at the same time, each on its own task in a private checkout '
                  'that was merged when its review passed.', '',
                  core.table(['', ''], [
                      ['Elapsed time (without hidden evaluations)', core.fmt_time(report['elapsed_seconds'])],
                      ['Agents busy on average', report['parallelism'] if report['parallelism'] is not None else '—'],
                      ['Merges', report['merges']],
                      ['Merges with conflicts (resolved by the model)', f'{report["merge_conflicts"]} ({report["merge_conflict_files"]} files)'],
                      ['Merges the model could not resolve', report['merges_failed']],
                      ['Time spent resolving conflicts', core.fmt_time(report['merge_agent_seconds'])]]), '']
    lines += ['## Hidden test results', '']
    if ev:
        when = 'at the end of the run, including the work on blocked tasks' if ev['label'] == 'final' else f'after {ev["label"]}'
        lines += [f'Scored by a private black-box suite the agent never saw, {when}: '
                  f'**{ev["passed"]} of {ev["total"]} checks passed**.', '',
                  core.table(['Category', 'Passed', 'Checks'],
                             [[core.label(k), v['passed'], v['total']] for k, v in ev['categories'].items()]), '']
        if ev['metrics'].get('ticks_per_second') is not None:
            lines += [f'Measured speed: {ev["metrics"]["ticks_per_second"]} ticks per second at about 2,000 individuals.', '']
        if ev.get('balance'):
            lines += ['Balance (how long plants, herbivores and carnivores coexist over 10,000 ticks; 0-100, in brackets the share of runs '
                      f'with all three alive at the end; a failed run counts as 0, runs over the time limit are left out and listed): '
                      f'example configuration {core.fmt_balance(ev, "fixed")}, '
                      f'the product\'s demo scenario {core.fmt_balance(ev, "demo")}. Collapse is allowed, so this is not a pass/fail check.', '']
        if len(report['evaluations']) > 1:
            lines += ['### Progress over the run', '',
                      core.table(['After', 'Tasks done', 'Checks passed', 'Checks due'],
                                 [[e['label'], e.get('done_tasks', '—'), e['passed'], e['due']] for e in report['evaluations']]), '']
    else:
        lines += ['This run was not scored.', '']
    shots = artifact.get('screenshots') or []
    lines += ['## User interface', '']
    if shots:
        lines += ['Screenshots written by the product itself (`./evosim ui --screenshots`). The tasks fix what the '
                  'interface must be able to do; its design was the agent\'s own choice.', '']
        lines += [f'![{pathlib.PurePath(s).stem}](screenshots/{s})\n' for s in shots]
    else:
        lines += ['The product wrote no screenshots.', '']
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


def index_readme(reports, harness_url, repo_url, analyses=()):
    body = core.comparison_markdown(reports).split('\n', 2)[2] if reports else '\nNo runs published yet.\n'
    lines = ['# Evolution Agent Benchmark: results', '',
             f'Published runs of the [Evolution Agent Benchmark]({harness_url or "#"}). Each coding agent, cloud or local, '
             'gets the same 28 dependent tasks and has to build an evolution simulation from an empty project on its own. '
             'Quality is scored by a private black-box test suite the agents never see.', '',
             'This page is generated; do not edit it by hand.', '']
    if analyses:
        lines += ['Written analyses: ' + ', '.join(f'[{a}]({a})' for a in analyses) + '.', '']
    lines += [body, '## Runs', '']
    for r in reports:
        folder = f'results/{r["profile"]}/{r["track"]}/{r["run_id"]}'
        link = f' · [executable]({repo_url}/releases/tag/{r["profile"]}-{r["track"]}-{r["run_id"]})' if repo_url and r.get('has_asset') else ''
        lines.append(f'- [{r["profile"]} · {r["track"]} · {r["run_id"]}]({folder}/README.md){link}')
    shown = [r for r in reports if r.get('screenshot')]
    if shown:
        lines += ['', '## Interfaces', '', 'The main view of each product, as designed by the agent.', '']
        for r in shown:
            folder = f'results/{r["profile"]}/{r["track"]}/{r["run_id"]}'
            lines += [f'**{r["profile"]} · {r["track"]} · {r["run_id"]}**', '', f'![{r["profile"]}]({folder}/{r["screenshot"]})', '']
    return '\n'.join(lines) + '\n'


def rebuild_index(results):
    reports = []
    for f in sorted(results.glob('results/*/*/*/report.json')):
        r = core.read(f)
        art = f.with_name('artifact.json')
        r['has_asset'] = art.exists() and core.read(art).get('build_ok', False)
        r['screenshot'] = 'screenshots/main.png' if f.with_name('screenshots').joinpath('main.png').is_file() else None
        reports.append(r)
    analyses = sorted(p.name for p in results.glob('ANALYSIS*.md'))
    (results / 'README.md').write_text(index_readme(reports, github_url(core.ROOT), github_url(results), analyses), encoding='utf-8')
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
    shutil.rmtree(dest / 'screenshots', ignore_errors=True)
    subprocess.run(['git', 'archive', '--format=zip', '-o', str(dest / 'source.zip'), 'HEAD'], cwd=run.workspace, check=True)

    artifact = {'asset': None, 'sha256': None, 'size_bytes': None, 'build_ok': False,
                'self_contained': False, 'self_contained_detail': '', 'screenshots': [], 'release_tag': name,
                'source_commit': core.git(run.workspace, 'rev-parse', 'HEAD'), 'packaged': core.now()}
    buildable = all((product / f).is_file() for f in ('setup.sh', 'build.sh'))
    print('  building in a fresh container ...' if buildable else '  no setup.sh/build.sh, skipping build', flush=True)
    shots = work / 'screenshots'; shots.mkdir()
    if buildable and build_product(cfg, product, work / 'build.log', shots):
        artifact['build_ok'] = True
        artifact['screenshots'] = collect_screenshots(shots, dest / 'screenshots')
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
    print(f'  screenshots: {len(artifact["screenshots"])}')
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
