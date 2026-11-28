# Development Workflow

## Branches

| Branch | Purpose | Who pushes |
|---|---|---|
| `main` | stable, demo-ready code | merged from `develop` only, via PR |
| `develop` | integration of all modules | merged from feature branches, via PR |
| `feature/users-nathan` | User & Host Profiles | Nathan |
| `feature/properties-sanjana` | Property & Search | Sanjana |
| `feature/bookings-bhavana` | Booking & Reservations | Bhavana |
| `feature/messaging-srija` | Messaging & Reviews | Srija |
| `feature/ai-angela` | Agentic AI & Recommendations | Angela |
| `feature/analytics-eric` | Analytics & Observability | Eric |

Short-lived sub-branches are fine too: `feature/bookings-bhavana-cancel-flow`.

Rules: no force-pushes to shared branches, no rewriting history on `main`/`develop`,
never commit `.env` or credentials.

## First-time setup (each member)

1. Accept the GitHub invitation (email, or https://github.com/notifications).
2. Clone and set up:

   ```bash
   git clone https://github.com/venkatasaibhavanay/data260-group1-airbnb.git
   cd data260-group1-airbnb
   git config user.name "Your Name"            # repo-local identity
   git config user.email "you@example.com"     # use the email on your GitHub account
   ./scripts/check-prereqs.sh
   ./scripts/setup-env.sh
   ./scripts/setup-python.sh
   cd frontend && npm install && cd ..
   ```

3. Check out your branch:

   ```bash
   git fetch origin
   git switch feature/bookings-bhavana          # use your own branch name
   ```

## Daily loop

```bash
git switch feature/<module>-<name>
git pull                                       # get your own latest work
git fetch origin && git merge origin/develop   # stay current with the team
./scripts/infra.sh up
./scripts/start-service.sh <your-service>      # terminal 1
./scripts/start-frontend.sh                    # terminal 2
# ... code ...
./scripts/run-tests.sh <your-service>
git add -p && git commit -m "booking: validate check-out after check-in"
git push -u origin feature/<module>-<name>
```

## Pull requests

1. Push your feature branch, then open a PR **into `develop`**:
   `gh pr create --base develop --fill` (or use the GitHub website).
2. PR description: what changed, how to test, screenshots for UI, any new env vars/topics/tables.
3. Checklist before requesting review:
   - [ ] `./scripts/run-tests.sh` passes
   - [ ] new endpoints show correctly in Swagger
   - [ ] no `.env`, secrets, `node_modules`, or `.venv` in the diff
   - [ ] shared files (`shared/`, `docker-compose.yml`, `.env.example`, `App.jsx`) changes called out
4. At least **one teammate approves**, two for changes to `shared/kafka` or infrastructure.
5. Merge with **Squash and merge** (or merge commit), then delete sub-branches.

## Merge to main (releases)

Before a milestone/demo: open a PR `develop → main`, run the full stack
(`infra.sh up`, `start-all-services.sh`, `health-check.sh --deps`, frontend), fix, then merge.
Tag it: `git tag v0.1-milestone1 && git push origin v0.1-milestone1`.

## Testing expectations

- Every endpoint: at least one success test and one failure/validation test.
- Business rules (e.g. overlapping bookings) get dedicated tests.
- Kafka: test that events you publish validate as `EventEnvelope`, and that consumers handle invalid messages.
- Integration tests against live containers go in `tests/integration/` (`--integration` flag).

## Contribution tracking

- Commit with your own GitHub-linked email so contributions show on your profile.
- Clear commit messages: `<module>: <what changed>`.
- Link PRs to GitHub Issues (`Closes #12`). Use a GitHub Project board with columns
  To do / In progress / Review / Done, with one label per module.
- GitHub **Insights → Contributors** shows each member's commits for grading.
