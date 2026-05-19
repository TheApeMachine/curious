#!/usr/bin/env node
import { runBootstrap } from "./commands/bootstrap.js";
import { runRoadmap } from "./commands/roadmap.js";
import { resolveConfig } from "./config.js";
import { inspectLastRun } from "./inspect-run.js";
import { initProject } from "./init-project.js";
import { Orchestrator, printStatus, resetState } from "./orchestrator.js";

function printHelp(): void {
  console.log(`curious — spec-driven agent workflow

Workflow:
  1. bootstrap   Agent explores repo → writes spec/SPEC.md
  2. roadmap     Agent expands spec → checkable Roadmap + Progress tasks
  3. run         Developer → Reviewer → Sync (repeat per roadmap task)

Commands:
  curious bootstrap [--verbose]
  curious roadmap [--verbose]
  curious run [options]
  curious status | reset | inspect [runId] | init [dir]

Run modes (curious run):
  (default)           Until done — T1.1 … until every ## Roadmap task is [x]
  --continuous        Same loop, stop only with Ctrl+C
  --cycle             One full cycle, then stop (alias for --cycles 1)
  --cycles N          N full cycles, then stop
  --once              Single phase only (develop OR review OR sync)

Examples:
  curious run                 # through the full roadmap, then exit
  curious run --continuous    # keep going after roadmap (manual stop)
  curious run --cycle         # one task only
  curious run --cycles 3      # three tasks, then stop

Project root: directory you run curious in (contains spec/SPEC.md)
Environment: CURSOR_API_KEY (required)
`);
}

function parseCyclesArg(argv: string[], index: number): number {
  const value = argv[index + 1];
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    console.error("--cycles requires a positive integer");
    process.exit(1);
  }
  return parsed;
}

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const command = argv[0] ?? "help";

  let configPath: string | undefined;
  let verbose = false;
  let once = false;
  let cycles: number | undefined;
  let untilDone = true;
  let continuous = false;

  for (let index = 1; index < argv.length; index++) {
    const arg = argv[index];
    if (arg === "--config" || arg === "-c") {
      configPath = argv[++index];
    } else if (arg === "--verbose" || arg === "-v") {
      verbose = true;
    } else if (arg === "--once") {
      once = true;
    } else if (arg === "--until-done") {
      untilDone = true;
    } else if (arg === "--continuous") {
      continuous = true;
      untilDone = false;
    } else if (arg === "--cycle") {
      cycles = 1;
    } else if (arg === "--cycles") {
      cycles = parseCyclesArg(argv, index);
      index++;
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      return;
    }
  }

  const modeFlags = [once, cycles !== undefined, continuous].filter(Boolean).length;
  if (modeFlags > 1) {
    console.error("Use only one of --once, --cycle, --cycles, or --continuous");
    process.exit(1);
  }

  switch (command) {
    case "bootstrap":
      await runBootstrap(configPath, verbose);
      break;
    case "roadmap":
      await runRoadmap(configPath, verbose);
      break;
    case "run": {
      const config = await resolveConfig({ configPath, requireSpec: true });
      const orchestrator = new Orchestrator(config, {
        verbose,
        once,
        cycles,
        untilDone,
      });
      await orchestrator.run();
      break;
    }
    case "status": {
      const config = await resolveConfig({ configPath, requireSpec: false });
      await printStatus(config);
      break;
    }
    case "reset": {
      const config = await resolveConfig({ configPath, requireSpec: false });
      await resetState(config);
      break;
    }
    case "init":
      await initProject(argv[1]?.startsWith("-") ? process.cwd() : (argv[1] ?? process.cwd()));
      break;
    case "inspect": {
      let inspectRunId: string | undefined;
      for (let index = 1; index < argv.length; index++) {
        const arg = argv[index];
        if (arg === "--config" || arg === "-c") {
          index++;
          continue;
        }
        if (!arg.startsWith("-")) {
          inspectRunId = arg;
          break;
        }
      }
      await inspectLastRun(configPath, inspectRunId);
      break;
    }
    case "help":
      printHelp();
      break;
    default:
      console.error(`Unknown command: ${command}`);
      printHelp();
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
