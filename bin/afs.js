#!/usr/bin/env node

import { Command } from 'commander';
import { execSync, spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PKG_ROOT = join(__dirname, '..');
const PROJECT_DIR = process.cwd();
const CONFIG_FILE = 'afs.config.json';

const pkg = JSON.parse(readFileSync(join(PKG_ROOT, 'package.json'), 'utf8'));

// ── Config ───────────────────────────────────────────────────

const DEFAULT_CONFIG = {
  apiPort: 8000,
  qdrantPort: 6333,
  redisPort: 6379,
  tikaPort: 9998,
  filestorePath: '',
  apiBaseUrl: '',
};

function loadConfig() {
  const configPath = resolve(PROJECT_DIR, CONFIG_FILE);
  let userConfig = {};

  if (existsSync(configPath)) {
    try {
      userConfig = JSON.parse(readFileSync(configPath, 'utf8'));
    } catch (err) {
      console.error(`\x1b[31mError parsing ${CONFIG_FILE}: ${err.message}\x1b[0m`);
      process.exit(1);
    }
  }

  return { ...DEFAULT_CONFIG, ...userConfig };
}

function configToEnv(config) {
  const env = {};
  // openaiApiKey from afs.config.json (lowest priority)
  if (config.openaiApiKey) env.OPENAI_API_KEY = config.openaiApiKey;
  // process.env overrides config file
  if (process.env.OPENAI_API_KEY) env.OPENAI_API_KEY = process.env.OPENAI_API_KEY;
  if (config.apiPort !== 8000) env.API_PORT = String(config.apiPort);
  if (config.qdrantPort !== 6333) env.QDRANT_PORT = String(config.qdrantPort);
  if (config.redisPort !== 6379) env.REDIS_PORT = String(config.redisPort);
  if (config.tikaPort !== 9998) env.TIKA_PORT = String(config.tikaPort);
  if (config.filestorePath) env.FILESTORE_BASE_PATH = config.filestorePath;
  if (config.apiBaseUrl) env.API_BASE_URL = config.apiBaseUrl;
  return env;
}

// ── Helpers ──────────────────────────────────────────────────

function dc(args, { stdio = 'inherit', env: extraEnv } = {}) {
  const config = loadConfig();
  const configEnv = configToEnv(config);
  const composeFile = join(PKG_ROOT, 'docker-compose.yml');
  const cmd = `docker compose -f "${composeFile}" -p agentic-filesystem ${args}`;
  execSync(cmd, {
    stdio,
    cwd: PKG_ROOT,
    env: { ...process.env, ...configEnv, ...extraEnv },
  });
}

function dcSpawn(args) {
  const config = loadConfig();
  const configEnv = configToEnv(config);
  const composeFile = join(PKG_ROOT, 'docker-compose.yml');
  const child = spawn(
    'docker',
    ['compose', '-f', composeFile, '-p', 'agentic-filesystem', ...args.split(' ')],
    {
      stdio: 'inherit',
      cwd: PKG_ROOT,
      env: { ...process.env, ...configEnv },
    }
  );
  child.on('close', (code) => process.exit(code ?? 0));
  return child;
}

function getConfig() {
  const config = loadConfig();
  const configPath = resolve(PROJECT_DIR, CONFIG_FILE);
  if (!existsSync(configPath)) {
    console.log(`\x1b[33mNo ${CONFIG_FILE} found in ${PROJECT_DIR}\x1b[0m`);
    console.log('Run \x1b[36mafs init\x1b[0m to create one.\n');
  }
  return config;
}

function waitForHealthy(config) {
  const maxWait = 90;
  const apiPort = config.apiPort || 8000;
  const qdrantPort = config.qdrantPort || 6333;
  let waited = 0;

  process.stdout.write(`Waiting for API (port ${apiPort})...`);
  while (waited < maxWait) {
    try {
      execSync(`curl -sf http://localhost:${apiPort}/health`, { stdio: 'ignore' });
      console.log(' \x1b[32mOK\x1b[0m');
      break;
    } catch {
      process.stdout.write('.');
      execSync('sleep 2');
      waited += 2;
    }
  }
  if (waited >= maxWait) {
    console.log(' \x1b[31mTIMEOUT\x1b[0m');
    console.log('API failed to start. Run: afs logs api');
    return false;
  }

  waited = 0;
  process.stdout.write(`Waiting for Qdrant (port ${qdrantPort})...`);
  while (waited < maxWait) {
    try {
      execSync(`curl -sf http://localhost:${qdrantPort}/healthz`, { stdio: 'ignore' });
      console.log(' \x1b[32mOK\x1b[0m');
      break;
    } catch {
      process.stdout.write('.');
      execSync('sleep 2');
      waited += 2;
    }
  }
  if (waited >= maxWait) {
    console.log(' \x1b[31mTIMEOUT\x1b[0m');
    return false;
  }

  console.log('\n\x1b[32mAll services ready!\x1b[0m');
  console.log(`  API Docs:  \x1b[36mhttp://localhost:${apiPort}/docs\x1b[0m`);
  console.log(`  Health:    \x1b[36mhttp://localhost:${apiPort}/health\x1b[0m`);
  console.log(`  Qdrant UI: \x1b[36mhttp://localhost:${qdrantPort}/dashboard\x1b[0m`);
  console.log('');
  return true;
}

// ── CLI ──────────────────────────────────────────────────────

const program = new Command();

program
  .name('afs')
  .description('Agentic Filesystem — tenant-scoped file storage & semantic search')
  .version(pkg.version);

program
  .command('init')
  .description('Create an afs.config.json in the current project')
  .action(() => {
    const configPath = resolve(PROJECT_DIR, CONFIG_FILE);
    if (existsSync(configPath)) {
      console.log(`\x1b[33m${CONFIG_FILE} already exists in ${PROJECT_DIR}\x1b[0m`);
      return;
    }

    const starter = {
      apiPort: 8000,
      qdrantPort: 6333,
      redisPort: 6379,
      tikaPort: 9998,
    };

    writeFileSync(configPath, JSON.stringify(starter, null, 2) + '\n');
    console.log(`\x1b[32mCreated ${CONFIG_FILE}\x1b[0m`);
    console.log('');
    console.log('Next steps:');
    console.log('  1. Set your OpenAI key via one of:');
    console.log('     a. Add \x1b[36m"openaiApiKey": "sk-..."\x1b[0m to afs.config.json');
    console.log('     b. Or export: \x1b[36mexport OPENAI_API_KEY=sk-...\x1b[0m');
    console.log('  2. Run \x1b[36mafs start\x1b[0m to launch services');
  });

program
  .command('start')
  .description('Start all services (build images if needed)')
  .option('--no-wait', 'Skip waiting for health checks')
  .action((opts) => {
    const config = getConfig();
    const configEnv = configToEnv(config);
    if (!configEnv.OPENAI_API_KEY) {
      console.log('\x1b[33mWarning: OPENAI_API_KEY is not set\x1b[0m');
      console.log('Embeddings and RAG will not work without it.');
      console.log('Set it via \x1b[36m"openaiApiKey"\x1b[0m in afs.config.json or \x1b[36mexport OPENAI_API_KEY=sk-...\x1b[0m\n');
    }
    console.log('\x1b[36mStarting Agentic Filesystem...\x1b[0m\n');
    dc('up -d --build');
    if (opts.wait) {
      console.log('');
      waitForHealthy(config);
    }
    dc('ps');
  });

program
  .command('stop')
  .description('Stop all services')
  .action(() => {
    console.log('\x1b[31mStopping Agentic Filesystem...\x1b[0m\n');
    dc('down');
    console.log('\x1b[32mAll services stopped.\x1b[0m');
  });

program
  .command('status')
  .description('Show service status and health checks')
  .action(() => {
    const config = getConfig();
    const apiPort = config.apiPort || 8000;
    const qdrantPort = config.qdrantPort || 6333;
    const redisPort = config.redisPort || 6379;

    dc('ps');
    console.log('\n\x1b[36mHealth Checks:\x1b[0m');
    try {
      execSync(`curl -sf http://localhost:${apiPort}/health`, { stdio: 'ignore' });
      console.log('  API:    \x1b[32mhealthy\x1b[0m');
    } catch {
      console.log('  API:    \x1b[31munreachable\x1b[0m');
    }
    try {
      execSync(`curl -sf http://localhost:${qdrantPort}/healthz`, { stdio: 'ignore' });
      console.log('  Qdrant: \x1b[32mhealthy\x1b[0m');
    } catch {
      console.log('  Qdrant: \x1b[31munreachable\x1b[0m');
    }
    try {
      execSync(`redis-cli -h localhost -p ${redisPort} ping`, { stdio: 'ignore' });
      console.log('  Redis:  \x1b[32mhealthy\x1b[0m');
    } catch {
      console.log('  Redis:  \x1b[33munreachable (or redis-cli not installed)\x1b[0m');
    }
  });

program
  .command('logs [service]')
  .description('Tail logs from all services or a specific one (api|worker|qdrant|redis|tika)')
  .action((service) => {
    const args = service ? `logs -f ${service}` : 'logs -f';
    dcSpawn(args);
  });

program
  .command('clean')
  .description('Wipe all data (volumes) and restart fresh')
  .action(() => {
    const config = getConfig();
    console.log('\x1b[31mWiping all data and restarting fresh...\x1b[0m');
    console.log('\x1b[33mThis will delete: uploaded files, Qdrant vectors, Redis state\x1b[0m\n');
    dc('down -v');
    console.log('\x1b[32mVolumes removed.\x1b[0m\n');
    console.log('\x1b[36mStarting fresh services...\x1b[0m\n');
    dc('up -d --build');
    console.log('');
    waitForHealthy(config);
    dc('ps');
  });

program
  .command('rebuild')
  .description('Force rebuild images and restart')
  .action(() => {
    const config = getConfig();
    console.log('\x1b[33mRebuilding images and restarting...\x1b[0m\n');
    dc('down');
    dc('build --no-cache');
    dc('up -d');
    console.log('');
    waitForHealthy(config);
    dc('ps');
  });

program.parse();
