# Berghain Bouncer Challenge Solver

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An algorithmic bouncer for the [Berghain Challenge] (Scenario 1) to help researchers and competitors rapidly iterate on admission strategies.

The goal: fill a 1000-capacity nightclub while meeting quota constraints (e.g., "≥40% locals", "≥80% wearing black") with as few rejections as possible.

## Problem
- People arrive one by one with binary attributes.
- You must immediately accept or reject each person.
- Constraints must be satisfied when the venue is full.
- Game ends when:
  - Venue is full (1000 people), or
  - You reject 20,000 people.

This is essentially an **online constrained optimization** problem.

## My Approach
- **Dynamic Quota Tracking:** Keep live counts of each constraint.
- **Feasibility Checks:** Reject people if accepting them would make quotas impossible.
- **Safety Margins:** Maintain each quota at least 10% ahead of minimum until 80% capacity.
- **Greedy Acceptance:** Prefer candidates from underrepresented groups.

## Results
- Placed **719th / 1303** on the official leaderboard.
- Submitted only for **one of three scenarios** (so score reflects partial participation).
- Solidly mid-pack, with clear room for optimization.

## Features

- **Constraint-aware decision logic** that prioritizes admissions needed to satisfy Berghain Scenario 1 requirements.
- **Robust request handling** with retry logic, jitter, and exponential backoff to stay below throttling thresholds.
- **Command-line interface** for providing player IDs and base URLs without editing code.
- **Detailed progress reporting** that logs effectiveness, remaining quotas, and rejection reasons as the run progresses.
- **Extensible configuration** via constants and environment variables for tuning throttling, logging, and retry behavior.

## Installation

### Prerequisites

- Python 3.11 or newer
- `pip` and (optionally) `venv`
- Access to the Listen Labs Berghain Challenge API

### Linux & macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt  # if present
pip install -r requirements-dev.txt  # optional tooling
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt  # if present
pip install -r requirements-dev.txt  # optional tooling
```

If `requirements.txt` is not provided, install the direct dependencies manually:

```bash
pip install requests
```

## Quickstart

1. Export your player ID and base URL (without the trailing slash):

    ```bash
    export BERGHAIN_BASE_URL="https://berghain.challenges.listenlabs.ai"
    export BERGHAIN_PLAYER_ID="00000000-0000-0000-0000-000000000000"
    ```

2. Run the solver:

    ```bash
    python BerghainSolver.py --base-url "$BERGHAIN_BASE_URL" --player-id "$BERGHAIN_PLAYER_ID"
    ```

3. Monitor the logs for admission efficiency, constraint coverage, and retry backoff behavior.

## Usage Guide

### Command-Line Interface

```text
usage: BerghainSolver.py --player-id PLAYER_ID --base-url BASE_URL

Scenario 1 Agent — helper-only version

options:
  --player-id PLAYER_ID   UUID assigned by the challenge website.
  --base-url BASE_URL     Base URL of the challenge instance (e.g., https://berghain.challenges.listenlabs.ai).
```

### Operational Flow

1. Request a new Scenario 1 game from `/new-game`.
2. Fetch the next person from `/decide-and-next`.
3. Decide acceptance based on outstanding attribute constraints.
4. Submit the decision and continue until the challenge reports `COMPLETED`.

## Configuration

| Parameter | Location | Default | Description |
| --- | --- | --- | --- |
| `REQUEST_TIMEOUT` | `BerghainSolver.py` | `(5, 30)` | Connect/read timeout tuple for HTTP requests. |
| `USER_AGENT` | `BerghainSolver.py` | `"HelperOnlyAgent-S1"` | Custom User-Agent header for challenge analytics. |
| `LOG_EVERY` | `BerghainSolver.py` | `100` | Frequency for progress log output. |
| `BASE_THROTTLE` | `BerghainSolver.py` | `0.01` | Minimum pause between person evaluations (seconds). |
| `MAX_RETRIES` | `BerghainSolver.py` | `5` | Maximum HTTP retries before failing the session. |
| `BACKOFF_BASE` | `BerghainSolver.py` | `0.2` | Base exponential backoff multiplier for HTTP 429 responses. |
| `MAX_BACKOFF` | `BerghainSolver.py` | `1.0` | Ceiling for retry delays.

To override values without editing source, export environment variables and consume them in a fork by wrapping the constants with `os.getenv(...)` lookups or external configuration files.

## Logging & Troubleshooting

- Standard output logs provide counts of processed people, admissions, efficiency, outstanding needs, and reason statistics.
- Retry and throttling events are implicit in slower cycles; instrument additional prints or a logging framework if needed.
- HTTP errors raise exceptions after `MAX_RETRIES` attempts; wrap `run_scenario1` in try/except for custom handling.
- A `KeyboardInterrupt` (`Ctrl+C`) cleanly exits the agent and prints `Interrupted.`
- Exit codes:
  - `0` — completed successfully (status `COMPLETED`).
  - `1` — interrupted by the user.
  - `>0` — unhandled exception (see stack trace).
- Common issues:
  - **HTTP 429 / rate limiting:** Increase `BASE_THROTTLE` or reduce logging frequency.
  - **Invalid player ID:** Ensure the UUID matches the challenge dashboard.
  - **Network errors:** Confirm VPN/firewall allows outbound HTTPS to the challenge host.

## Testing

Automated tests are not yet bundled. Prepare for future contributions by installing `pytest` and running:

```bash
pytest
```

Add new tests under `tests/` and ensure the suite remains green before opening a pull request.

## Roadmap

### Low Effort

- Add environment-variable support for all configuration constants.
- Publish sample `requirements.txt` and `requirements-dev.txt` files.
- Provide a ready-to-run Docker image for consistent execution.

### Moderate

- Introduce structured logging with log levels and JSON output mode.
- Implement unit tests for decision logic and HTTP retry helpers.
- Add support for multiple scenarios as they become available.

### Ambitious

- Build a pluggable strategy engine allowing experimentation with alternative admission heuristics.
- Integrate with a dashboard to visualize progress and constraint satisfaction in real time.
- Provide distributed execution for large-scale simulations across many player IDs.
- Explore reinforcement-learning approaches to optimize acceptance policies.

## Changelog

### v0.1.0

- Initial public release of the Scenario 1 helper-only agent.
- Includes CLI entry point, retry logic, and console logging.
- Supports configurable constants for timeouts, throttling, and retries.

## Contributing

1. Fork the repository and create a feature branch (`git checkout -b feature/my-improvement`).
2. Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines and keep functions pure when practical.
3. Run formatting (`python -m black .`) and static checks (`python -m flake8 .`) if available.
4. Add or update tests (`pytest`).
5. Ensure `python BerghainSolver.py --help` still succeeds.
6. Submit a pull request with a clear description, screenshots of console output when relevant, and link any related issues.

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

## FAQ

**Why is the solver limited to Scenario 1?**  
Scenario 1 is the publicly documented helper-only challenge; additional scenarios require different APIs and heuristics that are under exploration.

**Can I adjust the acceptance strategy?**  
Yes. Modify `should_accept` in `BerghainSolver.py` or wrap it with additional logic to enforce your own heuristics.

**How do I avoid HTTP 429 errors?**  
Increase `BASE_THROTTLE`, lower `LOG_EVERY`, or add exponential backoff via configuration overrides.

**Does the solver store any personal data?**  
No. All person attributes are processed in-memory and never persisted to disk.

**Can I run multiple games concurrently?**  
Launch separate processes with distinct player IDs or session cookies to avoid server-side throttling conflicts.

**Is Docker supported?**  
A Dockerfile is planned; in the meantime, run the solver inside a virtual environment to isolate dependencies.

**What happens if the challenge API changes?**  
Monitor the repository issues; update the endpoints or payload parsing logic within `run_scenario1` to match the new schema.

**How do I report bugs?**  
Open an issue with detailed reproduction steps, including command invocation, console output, and environment information.

