# TASK-010: Spatial search

## Depends on
TASK-001, TASK-004, TASK-008

## Goal
Find the organisms near a cell quickly, following the neighbour-search decision of TASK-001.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- A query returns all organisms within a radius of a cell, optionally only of one kind, correctly across the world's edges and without duplicates.
- Adding, moving and removing organisms keeps the index correct; a removed or moved organism is never returned from its old place.
- Results come back in a deterministic order.
- A randomised test compares at least 1,000 queries with a simple brute-force search, including small worlds and radii larger than the world.
- A measurement with about 2,000 organisms shows the index is faster than brute force; the numbers are recorded in the documentation.

## Your decisions
Decide these yourself and write down what you chose and why.

- The data structure.
- The query interface.

## Not part of this task
- Using the search for behaviour (TASK-013 onwards).
