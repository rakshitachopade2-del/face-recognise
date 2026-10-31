export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch(`/api${path}`, {method, credentials: 'same-origin',
    headers: form ? {} : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : form ? body : JSON.stringify(body)});
  if (!response.ok) {
    const error = await response.json().catch(() => ({detail: 'Request failed'}));
    throw new Error(typeof error.detail === 'string' ? error.detail.replaceAll('_', ' ') : 'Check the supplied fields.');
  }
  return response.json();
}
export function filesForm(files: FileList | null) {
  if (!files?.length) throw new Error('Choose at least one image.');
  const form = new FormData();
  Array.from(files).forEach(f => form.append('files', f));
  return form;
}
