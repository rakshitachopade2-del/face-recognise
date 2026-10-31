import { useCallback, useEffect, useRef, useState } from 'react';
import { api, filesForm } from './api';
import s from './App.module.css';

type Event = {id: string; name: string; expires: number; authorized: number};
type Person = {id: string; label: string; active: number; enrolled: number};
type Photo = {id: string; state: string; width: number; height: number};
type Job = {id: string; photo_id: string; kind: string; status: string; attempts: number; error: string | null};
type Status = {photos: Photo[]; jobs: Job[]; participants: Person[]; imports: {ordinal: number; state: string; reason: string | null}[]};
type Health = {synthetic: boolean; provider: string; configuration_state: string; enrollment_count: number};
type Diagnostics = {faces: {id: string; photo_id: string; bbox: number[]; status: string; quality: {score: number}}[]; proposals: {face_id: string; score: number | null; reason: string}[]};
const tabs = ['Workspace', 'Enrollment', 'Guest preview', 'Diagnostics', 'Report'];
const empty: Status = {photos: [], jobs: [], participants: [], imports: []};

export default function App() {
  const [health, setHealth] = useState<Health>();
  const [events, setEvents] = useState<Event[]>([]);
  const [event, setEvent] = useState('');
  const [tab, setTab] = useState('Workspace');
  const [status, setStatus] = useState<Status>(empty);
  const [person, setPerson] = useState('');
  const [gallery, setGallery] = useState<Photo[]>([]);
  const [preview, setPreview] = useState('');
  const [diagnostics, setDiagnostics] = useState<Diagnostics>();
  const [report, setReport] = useState<Record<string, unknown>>();
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const eventRef = useRef(event); eventRef.current = event;
  const previewRef = useRef(preview); previewRef.current = preview;
  const base = `/events/${event}`;
  const refresh = useCallback(async () => {
    const id = eventRef.current;
    if (id) {
      const data = await api<Status>(`/events/${id}/status`);
      if (id === eventRef.current) setStatus(data);
    }
  }, []);
  const act = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); setNotice('');
    try { await action(); await refresh(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  useEffect(() => { (async () => {
    await api('/session', 'POST');
    setHealth(await api<Health>('/health'));
    setEvents(await api<Event[]>('/events'));
  })().catch(e => setError(e.message)); }, []);
  useEffect(() => {
    setStatus(empty); setPerson(''); setPreview(''); setGallery([]); setDiagnostics(undefined); setReport(undefined);
    refresh().catch(e => setError(e.message));
    const timer = setInterval(() => refresh().catch(e => setError(e.message)), 2000);
    return () => clearInterval(timer);
  }, [event, refresh]);
  useEffect(() => {
    if (!event || !preview || tab !== 'Guest preview') return;
    let alive = true;
    const load = async () => {
      try {
        const data = await api<Photo[]>(`/events/${event}/participants/${preview}/gallery`);
        if (alive && previewRef.current === preview) setGallery(data);
      } catch (e) { if (alive) { setGallery([]); setPreview(''); setError((e as Error).message); } }
    };
    load(); const timer = setInterval(load, 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [event, preview, tab]);
  const active = status.participants.filter(p => p.active);
  const done = status.jobs.filter(j => j.status === 'complete').length;

  return <div className={s.app}>
    <aside className={s.sidebar}>
      <div className={s.brand}><span className={s.mark}>⌑</span> frame<span className={s.poc}>POC</span></div>
      <p className={s.eyebrow}>PHOTO RETRIEVAL LAB</p>
      <label className={s.eventLabel}>Current event<select aria-label="Current event" value={event} onChange={e => {setError(''); setEvent(e.target.value);}}>
        <option value="">Choose an event</option>{events.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
      </select></label>
      <nav aria-label="Main navigation">{tabs.map((name, i) => <button key={name} className={tab === name ? s.selected : ''} onClick={() => setTab(name)}><span>0{i + 1}</span>{name}</button>)}</nav>
      <div className={s.local}><span /> Local workspace<p>Files stay on this computer.<br/>One worker · Exact matching</p></div>
    </aside>
    <main>
      <header><div><p className={s.eyebrow}>EXPERIMENT / PHASES A + B</p><h1>{tab === 'Workspace' ? 'Every photo, in its place.' : tab}</h1></div><span className={s.badge}>{health?.synthetic ? 'SYNTHETIC MODE' : 'EXPERIMENTAL'}</span></header>
      <div className={s.warning}><strong>Operator-controlled identity simulator.</strong> No authentication, verified camera capture, or liveness checks. {health?.synthetic ? 'Colored rectangle fixtures test the pipeline; they do not test face recognition.' : `Operating point: ${health?.configuration_state}. Results are experimental.`}</div>
      {error && <div className={s.error} role="alert">{error}</div>}
      {notice && <div className={s.notice} role="status">{notice}</div>}
      {tab === 'Workspace' && <>
        <div className={s.stats}><article><span>Imported photos</span><strong>{status.photos.length}</strong></article><article><span>Jobs complete</span><strong>{done}<small> / {status.jobs.length}</small></strong></article><article><span>Enrolled participants</span><strong>{active.filter(p => p.enrolled).length}</strong></article></div>
        <div className={s.columns}>
          <section className={s.card}><p className={s.eyebrow}>01 / SET THE SCOPE</p><h2>Create an event</h2><p>Record permission before processing any photographs. This experiment is limited to consenting adults.</p>
            <form onSubmit={e => {e.preventDefault(); const data = new FormData(e.currentTarget); void act(async () => {
              const result = await api<{id: string}>('/events', 'POST', {name: data.get('name'), authorization: data.get('authorization'), days: Number(data.get('days'))});
              setEvents(await api<Event[]>('/events')); setEvent(result.id); setNotice('Event created with dataset processing authorization.');
            });}}>
              <label>Event name<input name="name" required placeholder="An authorized test event" maxLength={120}/></label>
              <label>Dataset permission record<input name="authorization" required placeholder="Local permission record / consented adults"/></label>
              <label>Data permission duration (days)<input name="days" type="number" min="1" max="30" defaultValue="30" required/></label>
              <button className={s.primary} disabled={busy}>Create event</button>
            </form>
          </section>
          <section className={s.card}><p className={s.eyebrow}>02 / ADD PHOTOGRAPHS</p><h2>Import a batch</h2><p>JPEG, PNG and supported HEIC. Exact duplicates reuse prior work; corrupt files are reported individually.</p>
            <form onSubmit={e => {e.preventDefault(); const input = e.currentTarget.elements.namedItem('photos') as HTMLInputElement; void act(async () => {
              const result = await api<{files: {state: string}[]}>(`${base}/photos`, 'POST', filesForm(input.files));
              setNotice(`Batch recorded: ${result.files.filter(f => f.state === 'imported').length} new, ${result.files.filter(f => f.state === 'duplicate').length} duplicate, ${result.files.filter(f => f.state === 'terminal_failure').length} failed.`); input.value = '';
            });}}><label className={s.drop}>Choose photographs<input aria-label="Photographs" name="photos" type="file" accept="image/jpeg,image/png,image/heic,image/heif" multiple required disabled={!event}/><small>Maximum 25 MiB / file · 40 million pixels · 100 files / batch</small></label><button className={s.primary} disabled={busy || !event}>Import photographs</button></form>
            {health?.synthetic && <p className={s.hint}>Use the generated files in <code>var/fixtures/</code>. Real photographs require an approved real provider.</p>}
          </section>
        </div>
        <section className={s.card}><div className={s.sectionTitle}><h2>Processing queue</h2><span>{status.jobs.length ? 'Refreshes every 2 seconds' : 'Waiting for your first import'}</span></div>
          <progress aria-label="Processing progress" max={Math.max(status.jobs.length, 1)} value={done}/>
          {status.jobs.length > 0 && <div className={s.tableWrap}><table><thead><tr><th>Photo</th><th>Stage</th><th>Status</th><th>Attempts</th><th>Action</th></tr></thead><tbody>{status.jobs.map(j => <tr key={j.id}><td>{j.photo_id.slice(0, 8)}</td><td>{j.kind}</td><td>{j.status.replaceAll('_', ' ')}{j.error && <small>{j.error.replaceAll('_', ' ')}</small>}</td><td>{j.attempts}</td><td>{j.status.endsWith('failure') && <button disabled={busy} onClick={() => void act(async () => {await api(`${base}/jobs/${j.id}/retry`, 'POST');})}>Retry</button>}</td></tr>)}</tbody></table></div>}
          {status.imports.filter(i => i.reason).map((i, n) => <p key={n} className={s.error}>File {i.ordinal + 1}: {i.reason?.replaceAll('_', ' ')}</p>)}
        </section>
      </>}
      {tab === 'Enrollment' && <div className={s.columns}>
        <section className={s.card}><h2>Record participant consent</h2><p>Separate from dataset authorization. The participant explicitly agrees to photo retrieval for this event.</p>
          <form onSubmit={e => {e.preventDefault(); const data = new FormData(e.currentTarget); void act(async () => {
            const p = await api<{participant_id: string}>(`${base}/participants`, 'POST', {label: data.get('label'), basis: data.get('basis')}); setPerson(p.participant_id); setNotice('Purpose-specific consent recorded. Add enrollment references next.');
          });}}><label>Participant label<input name="label" required placeholder="Use an opaque test label"/></label><label>Active consent record<input name="basis" required placeholder="Permission for photo retrieval"/></label><label className={s.check}><input type="checkbox" required/>I have this adult participant’s explicit permission.</label><button className={s.primary} disabled={!event || busy}>Record consent</button></form>
        </section>
        <section className={s.card}><h2>Enroll test participant</h2><p>Supply exactly {health?.enrollment_count ?? 1} independent reference image(s). Zero-face, multi-face and inadequate inputs are rejected. Raw references are not retained.</p>
          <form onSubmit={e => {e.preventDefault(); const input = e.currentTarget.elements.namedItem('references') as HTMLInputElement; void act(async () => {
            await api(`${base}/participants/${person}/enrollment`, 'POST', filesForm(input.files)); input.value = ''; setPreview(''); setGallery([]); setNotice('Enrolled. Existing compatible photographs are queued for matching.');
          });}}><label>Participant<select aria-label="Participant" value={person} onChange={e => setPerson(e.target.value)} required><option value="">Select participant</option>{active.map(p => <option key={p.id} value={p.id}>{p.label}{p.enrolled ? ' · enrolled' : ''}</option>)}</select></label><label>Reference images<input name="references" aria-label="Reference images" type="file" accept="image/jpeg,image/png,image/heic,image/heif" multiple required/></label><button className={s.primary} disabled={!person || busy}>Enroll participant</button></form>
          <p className={s.hint}>Test enrollment only. Image selection does not verify identity or prevent spoofing.</p>
          {person && <button className={s.danger} disabled={busy} onClick={() => void act(async () => {await api(`${base}/participants/${person}/withdraw`, 'POST'); setPerson(''); setPreview(''); setGallery([]); setNotice('Withdrawn. Enrollment data and gallery links deleted; matching and access disabled.');})}>Withdraw consent & delete enrollment</button>}
        </section>
      </div>}
      {tab === 'Guest preview' && <>
        <section className={s.card}><h2>Simulate a participant’s gallery</h2><p>Only released full photographs appear here. A group photo may belong to several participants.</p><label>Preview as<select aria-label="Preview as" value={preview} disabled={busy} onChange={e => {const id = e.target.value; setGallery([]); setPreview(''); if (id) void act(async () => {await api(`${base}/participants/${id}/preview`, 'POST'); setPreview(id);});}}><option value="">Select enrolled participant</option>{active.filter(p => p.enrolled).map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label></section>
        {!gallery.length && <div className={s.empty}><span>⌑</span><h2>{preview ? 'No photographs yet.' : 'Choose a participant to preview.'}</h2><p>{preview ? 'Matches will appear as eligible photographs finish processing. An empty gallery is a valid result.' : 'This is a local identity simulator.'}</p></div>}
        <div className={s.gallery}>{gallery.map(p => <article className={s.photo} key={p.id}><img src={`/api${base}/participants/${preview}/gallery/${p.id}/media`} alt="Released photograph"/><button disabled={busy} onClick={() => void act(async () => {await api(`${base}/participants/${preview}/gallery/${p.id}/reject`, 'POST'); setGallery(g => g.filter(x => x.id !== p.id)); setNotice('Removed. This association is suppressed on future retries.');})}>Not me</button></article>)}</div>
      </>}
      {tab === 'Diagnostics' && <>
        <section className={s.card}><h2>Operator diagnostics</h2><p>Private boxes, quality signals and candidate evidence. These are never included in the guest gallery response. Scores are not probabilities.</p><button className={s.primary} disabled={!event || busy} onClick={() => void act(async () => setDiagnostics(await api<Diagnostics>(`${base}/diagnostics`)))}>Inspect detections</button></section>
        <div className={s.gallery}>{diagnostics && status.photos.map(p => <article className={s.photo} key={p.id}><div className={s.overlay}><img src={`/api${base}/photos/${p.id}/operator-media`} alt="Operator diagnostic"/><svg viewBox={`0 0 ${p.width} ${p.height}`} aria-label="Detection boxes">{diagnostics.faces.filter(f => f.photo_id === p.id).map(f => <rect key={f.id} x={f.bbox[0]} y={f.bbox[1]} width={f.bbox[2]} height={f.bbox[3]} fill="none" stroke="#00ffb3" strokeWidth={Math.max(2, p.width / 250)}/>)}</svg></div>{diagnostics.faces.filter(f => f.photo_id === p.id).map(f => <p key={f.id}>{f.status} · {diagnostics.proposals.find(m => m.face_id === f.id)?.reason ?? 'pending match'}<small>Detection score {f.quality.score.toFixed(3)} · Candidate score {diagnostics.proposals.find(m => m.face_id === f.id)?.score?.toFixed(3) ?? '—'}</small></p>)}</article>)}</div>
      </>}
      {tab === 'Report' && <section className={s.card}><p className={s.eyebrow}>EVIDENCE, NOT ESTIMATES</p><h2>Experiment report</h2><p>Export an aggregate configuration and run snapshot. Real recognition accuracy, cost, fairness and liveness remain NOT MEASURED. Synthetic runs cannot enter real-model benchmark summaries.</p><button className={s.primary} disabled={!event || busy} onClick={() => void act(async () => setReport(await api<Record<string, unknown>>(`${base}/report`, 'POST')))}>Generate report</button>{report && <><button onClick={() => {const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'})); const a = document.createElement('a'); a.href = url; a.download = 'aggregate-experiment-report.json'; a.click(); URL.revokeObjectURL(url);}}>Download JSON</button><pre>{JSON.stringify(report, null, 2)}</pre></>}</section>}
      <footer>Frame / Local proof of concept <span>No production accuracy or cost claim.</span></footer>
    </main>
  </div>;
}
