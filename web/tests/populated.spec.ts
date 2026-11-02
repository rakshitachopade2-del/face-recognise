import { test, expect, type Page } from '@playwright/test';
import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { writeFileSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '../..');
const python = path.join(root, '.venv/bin/python');
const privateDir = path.resolve(root, process.env.FACE_BROWSER_DATA_DIR || 'var/browser-tests');
const env = {...process.env, FACE_DATA_DIR: privateDir, FACE_CONFIG: path.join(root, 'configs/synthetic.json')};
let worker: ChildProcess | undefined;
function startWorker() {
  worker = spawn(python, ['-m', 'server.worker'], {cwd: root, env, stdio: 'ignore'});
}
async function stopWorker() {
  if (!worker || worker.exitCode !== null || worker.signalCode !== null) return;
  const exit = once(worker, 'exit');
  worker.kill('SIGTERM');
  await exit;
  worker = undefined;
}
test.beforeAll(startWorker);
test.afterAll(stopWorker);

type Job = {id: string; photo_id: string; kind: string; status: string; attempts: number};
type State = {jobs: Job[]; photos: {id: string}[]; participants: {id: string; active: number}[]};
async function state(page: Page, event: string): Promise<State> {
  const response = await page.request.get(`/api/events/${event}/status`);
  expect(response.status()).toBe(200);
  return response.json();
}
async function complete(page: Page, event: string) {
  await expect.poll(async () => (await state(page, event)).jobs.every(j => ['complete', 'superseded'].includes(j.status)),
    {timeout: 25000}).toBe(true);
}
async function createEvent(page: Page, suffix: string) {
  await page.getByRole('button', {name: '01 Workspace'}).click();
  await page.getByLabel('Event name').fill(`SYNTHETIC publication check ${suffix} ${Date.now()}`);
  await page.getByLabel('Dataset permission record').fill('Generated colored rectangles only; no human photographs');
  const response = page.waitForResponse(r => r.url().endsWith('/api/events') && r.request().method() === 'POST');
  await page.getByRole('button', {name: 'Create event', exact: true}).click();
  const id: string = (await (await response).json()).id;
  await expect(page.getByLabel('Current event')).toHaveValue(id);
  return id;
}
async function upload(page: Page, event: string, names: string[]) {
  await page.getByRole('button', {name: '01 Workspace'}).click();
  await page.getByLabel('Photographs', {exact: true}).setInputFiles(names.map(n => path.join(root, 'var/fixtures', n)));
  const response = page.waitForResponse(r => r.url().endsWith(`/events/${event}/photos`) && r.request().method() === 'POST');
  await page.getByRole('button', {name: 'Import photographs'}).click();
  const result: {files: {photo_id: string; state: string}[]} = await (await response).json();
  await expect(page.getByRole('button', {name: 'Import photographs'})).toBeEnabled();
  return result.files;
}
async function enroll(page: Page, event: string, color: string) {
  await page.getByRole('button', {name: '02 Enrollment'}).click();
  await page.getByLabel('Participant label').fill(`SYNTHETIC ${color}`);
  await page.getByLabel('Active consent record').fill('Synthetic test consent; no real participant');
  await page.getByRole('checkbox').check();
  const consent = page.waitForResponse(r => r.url().endsWith(`/events/${event}/participants`) && r.request().method() === 'POST');
  await page.getByRole('button', {name: 'Record consent', exact: true}).click();
  const id: string = (await (await consent).json()).participant_id;
  await expect(page.getByLabel('Participant', {exact: true})).toHaveValue(id);
  await page.getByLabel('Reference images', {exact: true}).setInputFiles(path.join(root, `var/fixtures/enroll-${color}.png`));
  await page.getByRole('button', {name: 'Enroll participant', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('Enrolled.');
  await complete(page, event);
  return id;
}
async function preview(page: Page, event: string, person: string, expectedPhotos: string[]) {
  await page.getByRole('button', {name: '03 Guest preview'}).click();
  await page.getByLabel('Preview as').selectOption('');
  await page.getByLabel('Preview as').selectOption(person);
  await expect(page.getByLabel('Preview as')).toBeEnabled();
  await expect(page.getByAltText('Released photograph')).toHaveCount(expectedPhotos.length, {timeout: 15000});
  await expect.poll(async () => {
    const response = await page.request.get(`/api/events/${event}/participants/${person}/gallery`);
    if (!response.ok()) return [];
    return (await response.json()).map((p: {id: string}) => p.id).sort();
  }).toEqual([...expectedPhotos].sort());
  for (const photo of expectedPhotos) {
    const image = page.locator(`img[src$="/gallery/${photo}/media"]`);
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
  }
}

test('populated two-event lifecycle with shared group, late work, retry/restart and withdrawal', async ({page}) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  const checks: Record<string, unknown> = {};
  await page.goto('/');
  await expect(page.getByText('SYNTHETIC MODE')).toBeVisible();

  const a = await createEvent(page, 'A');
  const imports = await upload(page, a, ['gallery-group.png', 'gallery-red.png', 'gallery-unknown.png']);
  expect(imports.map(i => i.state)).toEqual(['imported', 'imported', 'imported']);
  const [group, redOnly, unknown] = imports.map(i => i.photo_id);
  await complete(page, a);
  const initialProcesses = (await state(page, a)).jobs.filter(j => j.kind === 'process').length;
  const red = await enroll(page, a, 'red');
  await preview(page, a, red, [group, redOnly]);
  const green = await enroll(page, a, 'green');
  await preview(page, a, green, [group]);
  await preview(page, a, red, [group, redOnly]);
  expect((await state(page, a)).jobs.filter(j => j.kind === 'process')).toHaveLength(initialProcesses);
  checks.late_enrollment = {passed: true, detection_jobs_before: 3, detection_jobs_after: 3};
  checks.group_photo = {passed: true, distinct_participant_galleries: 2};
  checks.expected_initial_results = {red: 2, green: 1, unknown_deliveries: 0};
  const unknownAccess = await page.request.get(`/api/events/${a}/participants/${red}/gallery/${unknown}/media`);
  expect(unknownAccess.status()).toBe(403);

  const before = await state(page, a);
  const duplicate = await upload(page, a, ['gallery-group.png']);
  expect(duplicate[0]).toMatchObject({photo_id: group, state: 'duplicate'});
  expect((await state(page, a)).jobs).toHaveLength(before.jobs.length);
  expect((await state(page, a)).photos).toHaveLength(3);
  checks.duplicate_import = {passed: true, additional_jobs: 0, additional_photos: 0};

  const lateRed = (await upload(page, a, ['gallery-red-late.png']))[0].photo_id;
  await complete(page, a);
  await preview(page, a, red, [group, redOnly, lateRed]);
  await preview(page, a, green, [group]);
  checks.late_photo = {passed: true, red_gallery: 3, green_gallery: 1};
  await page.screenshot({path: path.join(root, process.env.FACE_BROWSER_RESULTS_DIR || 'var', 'screenshots/populated-group.png'), fullPage: true});

  await preview(page, a, red, [group, redOnly, lateRed]);
  await page.locator('article').filter({has: page.locator(`img[src$="/gallery/${group}/media"]`)}).getByRole('button', {name: 'Not me'}).click();
  await expect(page.getByRole('status')).toContainText('suppressed');
  await expect(page.getByAltText('Released photograph')).toHaveCount(2);

  // Test-only fault injection in the isolated synthetic database. No debug endpoint is added to the app.
  await complete(page, a);
  await stopWorker();
  const replay = (await state(page, a)).jobs.find(j => j.kind === 'match' && j.photo_id === group)!;
  execFileSync(python, ['-c', `
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as db:
    db.execute("UPDATE jobs SET status='retryable_failure',error='synthetic_test_replay' WHERE id=?",(sys.argv[2],))
`, path.join(privateDir, 'metadata.db'), replay.id], {cwd: root, env});
  await page.getByRole('button', {name: '01 Workspace'}).click();
  await page.getByRole('button', {name: 'Retry', exact: true}).click();
  await expect.poll(async () => (await state(page, a)).jobs.find(j => j.id === replay.id)?.status).toBe('pending');
  startWorker();
  await complete(page, a);
  await page.reload();
  await page.getByLabel('Current event').selectOption(a);
  await preview(page, a, red, [redOnly, lateRed]);
  await preview(page, a, green, [group]);
  checks.not_me = {passed: true, worker_restarted: true, browser_reloaded: true,
    retried_match_job_completed: true, red_gallery: 2, unaffected_green_gallery: 1};

  const b = await createEvent(page, 'B');
  const bGroup = (await upload(page, b, ['gallery-group.png']))[0];
  expect(bGroup.state).toBe('imported');
  expect(bGroup.photo_id).not.toBe(group);
  await complete(page, b);
  const bRed = await enroll(page, b, 'red');
  await preview(page, b, bRed, [bGroup.photo_id]);
  const crossGallery = await page.request.get(`/api/events/${a}/participants/${red}/gallery`);
  const crossMedia = await page.request.get(`/api/events/${a}/participants/${red}/gallery/${redOnly}/media`);
  const wrongAsset = await page.request.get(`/api/events/${b}/photos/${group}/operator-media`);
  expect(crossGallery.status()).toBe(403);
  expect(crossMedia.status()).toBe(403);
  expect(wrongAsset.status()).toBe(404);
  expect((await state(page, b)).photos.map(p => p.id)).toEqual([bGroup.photo_id]);
  checks.event_isolation = {passed: true, events: 2, same_bytes_have_distinct_event_assets: true,
    cross_gallery_http: 403, cross_media_http: 403, wrong_event_asset_http: 404};

  await page.getByLabel('Current event').selectOption(a);
  await preview(page, a, red, [redOnly, lateRed]);
  const oldCookies = (await page.context().cookies()).map(c => `${c.name}=${c.value}`).join('; ');
  await stopWorker();
  const lateGroup = (await upload(page, a, ['gallery-group-late.png']))[0].photo_id;
  await page.getByRole('button', {name: '02 Enrollment'}).click();
  await page.getByLabel('Participant', {exact: true}).selectOption(red);
  await page.getByRole('button', {name: 'Withdraw consent & delete enrollment'}).click();
  await expect(page.getByRole('status')).toContainText('Withdrawn.');
  startWorker();
  await complete(page, a);
  const deniedGallery = await page.request.get(`/api/events/${a}/participants/${red}/gallery`, {headers: {Cookie: oldCookies}});
  const deniedMedia = await page.request.get(`/api/events/${a}/participants/${red}/gallery/${redOnly}/media`, {headers: {Cookie: oldCookies}});
  expect(deniedGallery.status()).toBe(401);
  expect(deniedMedia.status()).toBe(401);
  const deniedPreview = await page.request.post(`/api/events/${a}/participants/${red}/preview`, {headers: {Origin: 'http://127.0.0.1:5177'}});
  expect(deniedPreview.status()).toBe(403);
  await preview(page, a, green, [group, lateGroup]);
  const deleted = JSON.parse(execFileSync(python, ['-c', `
import sqlite3,sys,json
with sqlite3.connect(sys.argv[1]) as db:
    result={t:db.execute(f"SELECT COUNT(*) FROM {t} WHERE event_id=? AND participant_id=?",sys.argv[2:4]).fetchone()[0]
            for t in ('enrollments','released_associations')}
print(json.dumps(result))
`, path.join(privateDir, 'metadata.db'), a, red], {cwd: root, env, encoding: 'utf8'}));
  expect(deleted).toEqual({enrollments: 0, released_associations: 0});
  checks.withdrawal = {passed: true, queued_photo_completed_after_revocation: true,
    stale_session_gallery_http: 401, stale_session_media_http: 401, new_preview_http: 403,
    deleted_templates: true, withdrawn_participant_releases: 0, active_green_gallery: 2};
  await page.getByLabel('Current event').selectOption(b);
  await preview(page, b, bRed, [bGroup.photo_id]);
  checks.other_event_after_withdrawal = {passed: true, gallery_count: 1};
  expect(errors).toEqual([]);
  writeFileSync(path.join(root, process.env.FACE_BROWSER_RESULTS_DIR || 'var', 'populated-browser-outcomes.json'), JSON.stringify({
    synthetic_only: true, recognition_accuracy: 'NOT MEASURED', status: 'passed', checks,
    uncaught_browser_errors: errors.length,
  }, null, 2) + '\n');
});

test('incompatible enrollment shows reason and becomes previewable after re-enrollment', async ({page}) => {
  // Generated rectangles only, in this browser run's isolated DB. Previous policy used 3 references.
  const seeded = JSON.parse(execFileSync(python, ['-c', `
import json
from pathlib import Path
from server.config import Settings
from server.service import Service
from server.worker import Worker
from scripts.make_fixtures import fixture
s = Settings.environment()
old_config = s.operating_point().model_copy(update={'enrollment_count': 3, 'version': 'browser-previous-policy'})
path = s.data_dir / 'previous-policy.json'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(old_config.model_dump_json())
old = Service(s.model_copy(update={'config_path': path}))
e = old.create_event('SYNTHETIC C0.1 readiness', 'Generated rectangles only')
p = old.consent(e, 'SYNTHETIC policy participant', 'Synthetic test consent')['participant_id']
old.enroll(e, p, [fixture(['red'])] * 3)
old.import_one(e, fixture(['red'], variant=2), 'synthetic', 0)
w = Worker(old)
while w.run_once(): pass
Service(s).activate_configuration(e)
print(json.dumps({'event':e,'person':p}))
`], {cwd: root, env, encoding: 'utf8'})) as {event: string; person: string};
  await page.goto('/');
  await expect(page.getByText('SYNTHETIC MODE')).toBeVisible();
  await page.getByLabel('Current event').selectOption(seeded.event);
  await page.getByRole('button', {name: '02 Enrollment'}).click();
  await page.getByLabel('Participant', {exact: true}).selectOption(seeded.person);
  await expect(page.getByText('Re-enrollment required: reference policy changed.')).toBeVisible();
  await page.getByRole('button', {name: '03 Guest preview'}).click();
  await expect(page.getByLabel('Preview as').locator(`option[value="${seeded.person}"]`)).toHaveCount(0);
  await page.getByRole('button', {name: '02 Enrollment'}).click();
  await page.getByLabel('Reference images', {exact: true}).setInputFiles(path.join(root, 'var/fixtures/enroll-red.png'));
  await page.getByRole('button', {name: 'Enroll participant', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('Enrolled.');
  await expect(page.getByText('Re-enrollment required: reference policy changed.')).toHaveCount(0);
  await page.getByRole('button', {name: '03 Guest preview'}).click();
  await page.getByLabel('Preview as').selectOption(seeded.person);
  await expect(page.getByAltText('Released photograph')).toHaveCount(1);
});
