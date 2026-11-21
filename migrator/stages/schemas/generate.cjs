// Generate local Carepatron input schemas. No server or API calls.
const fs = require('node:fs');
const path = require('node:path');
const { buildSync } = require('../../../carepatron/node_modules/esbuild');
const { z } = require('../../../carepatron/node_modules/zod');

const modelFile = path.join(__dirname, '../../../carepatron/src/model.ts');
const outputDirectory = __dirname;
const checkOnly = process.argv.includes('--check');

function loadModels() {

  const build = buildSync({
    entryPoints: [modelFile],
    bundle: true,
    platform: 'node',
    format: 'cjs',
    write: false,
  });
  const javascript = build.outputFiles[0].text;

  const modelModule = { exports: {} };
  const executeModule = new Function(
    'module',
    'exports',
    'require',
    javascript,
  );
  executeModule(modelModule, modelModule.exports, require);
  return modelModule.exports;
}

const models = loadModels();

const inputModels = {
  practice: models.PracticeFields.partial().strict(),
  locations: models.createSchema('locations'), // LocationFields
  services: models.createSchema('services'), // ServiceFields
  team: models.createSchema('team'), // TeamMemberFields
  payers: models.createSchema('payers'), // PayerFields
  clients: models.createSchema('clients'), // ClientFields
  policies: models.createSchema('policies'), // InsurancePolicyFields
  appointments: models.createSchema('appointments'), // AppointmentFields
  notes: models.createSchema('notes'), // NoteFields
};

if (!checkOnly) {
  fs.mkdirSync(outputDirectory, { recursive: true });
}

for (const [name, inputModel] of Object.entries(inputModels)) {
  const recordSchema = z.toJSONSchema(inputModel, {
    io: 'input',
    unrepresentable: 'any',
  });

  let fileSchema = recordSchema;
  if (name !== 'practice') {
    fileSchema = {
      $schema: recordSchema.$schema,
      type: 'array',
      items: recordSchema,
    };
  }

  const file = path.join(outputDirectory, `${name}.schema.json`);
  const content = JSON.stringify(fileSchema, null, 2) + '\n';

  if (checkOnly) {
    if (fs.readFileSync(file, 'utf8') !== content) {
      throw new Error(`Schema is stale: ${name}`);
    }
  } else {
    fs.writeFileSync(file, content);
  }
}

console.log(
  `${checkOnly ? 'Checked' : 'Generated'} ${Object.keys(inputModels).length} schemas.`,
);
