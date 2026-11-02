import { test, expect } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '../..');
let worker: ChildProcess;
test.beforeAll(() => {
  worker = spawn(path.join(root, '.venv/bin/python'), ['-m', 'server.worker'], {
    cwd: root, env: {...process.env, FACE_DATA_DIR: path.resolve(root, process.env.FACE_BROWSER_DATA_DIR || 'var/browser-tests')}, stdio: 'ignore'});
});
test.afterAll(() => { worker?.kill('SIGTERM'); });

test('synthetic operator loop: import, enroll, gallery, correction, withdrawal, report', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.getByText('SYNTHETIC MODE')).toBeVisible();
  await page.getByLabel('Event name').fill(`Browser synthetic ${Date.now()}`);
  await page.getByLabel('Dataset permission record').fill('Generated rectangle fixture authorization; no humans');
  await page.getByRole('button', {name: 'Create event', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('Event created');
  await page.getByLabel('Photographs', {exact: true}).setInputFiles([
    path.join(root, 'var/fixtures/gallery-group.png'), path.join(root, 'var/fixtures/gallery-unknown.png'),
    path.join(root, 'var/fixtures/corrupt.png')]);
  await page.getByRole('button', {name: 'Import photographs'}).click();
  await expect(page.getByRole('status')).toContainText('2 new, 0 duplicate, 1 failed');
  await expect(page.getByText('File 3: corrupt or unsupported image')).toBeVisible();
  await expect(page.getByRole('cell', {name: 'complete', exact: true})).toHaveCount(4, {timeout: 20000});
  await page.getByLabel('Photographs', {exact: true}).setInputFiles(path.join(root, 'var/fixtures/gallery-group.png'));
  await page.getByRole('button', {name: 'Import photographs'}).click();
  await expect(page.getByRole('status')).toContainText('0 new, 1 duplicate');
  await page.screenshot({path: path.join(root, process.env.FACE_BROWSER_RESULTS_DIR || 'var', 'screenshots/workspace.png'), fullPage: true});
  await page.getByRole('button', {name: '02 Enrollment'}).click();
  await page.getByLabel('Participant label').fill('Synthetic red');
  await page.getByLabel('Active consent record').fill('Synthetic consent record');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', {name: 'Record consent', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('consent recorded');
  await page.getByLabel('Reference images', {exact: true}).setInputFiles(path.join(root, 'var/fixtures/enroll-red.png'));
  await page.getByRole('button', {name: 'Enroll participant', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('Enrolled.');
  await page.getByRole('button', {name: '03 Guest preview'}).click();
  await page.getByLabel('Preview as').selectOption({label: 'Synthetic red'});
  await expect(page.getByAltText('Released photograph')).toHaveCount(1, {timeout: 20000});
  await expect(page.getByAltText('Released photograph')).toBeVisible();
  expect(await page.getByAltText('Released photograph').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  await page.screenshot({path: path.join(root, process.env.FACE_BROWSER_RESULTS_DIR || 'var', 'screenshots/gallery.png'), fullPage: true});
  await page.getByRole('button', {name: 'Not me', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'No photographs yet.'})).toBeVisible();
  await page.getByRole('button', {name: '02 Enrollment'}).click();
  await page.getByRole('button', {name: 'Withdraw consent & delete enrollment'}).click();
  await expect(page.getByRole('status')).toContainText('Withdrawn.');
  await page.getByRole('button', {name: '04 Diagnostics'}).click();
  await page.getByRole('button', {name: 'Inspect detections'}).click();
  await expect(page.getByAltText('Operator diagnostic')).toHaveCount(2);
  await page.getByRole('button', {name: '05 Report'}).click();
  await page.getByRole('button', {name: 'Generate report'}).click();
  await expect(page.locator('pre')).toContainText('SYNTHETIC PIPELINE TEST');
  await expect(page.locator('pre')).toContainText('not_measured');
  expect(errors).toEqual([]);
});

test('mobile shell has no horizontal overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  await expect(page.getByRole('heading', {name: 'Every photo, in its place.'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({path: path.join(root, process.env.FACE_BROWSER_RESULTS_DIR || 'var', 'screenshots/mobile.png'), fullPage: true});
});
