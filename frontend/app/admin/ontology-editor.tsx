'use client'

import { useState, useEffect, useCallback } from 'react'
import { useWorkspace } from '../workspace-context'
import { useAuth } from '../auth-context'

/**
 * v2 本体编辑器（WP9）。
 *
 * 三个子 tab：Objects / Links / Actions。
 * 每个：表格 + 行级编辑/删除 + 顶部新建。全字段表单（spec §5.3）。
 * 写操作走 POST/PUT/DELETE /api/admin/customers/{ws}/ontology/{type}。
 */

type Kind = 'objects' | 'links' | 'actions'

export function OntologyEditor() {
  const { selectedWorkspace } = useWorkspace()
  const [kind, setKind] = useState<Kind>('objects')
  if (!selectedWorkspace) return <div style={{ padding: 12, color: '#999' }}>未选 workspace</div>
  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        {(['objects', 'links', 'actions'] as const).map(k => (
          <button key={k} onClick={() => setKind(k)} style={{
            padding: '6px 14px', borderRadius: 6,
            border: `1px solid ${kind === k ? '#2563eb' : '#d1d5db'}`,
            background: kind === k ? '#2563eb' : '#fff',
            color: kind === k ? '#fff' : '#374151', cursor: 'pointer', fontSize: 13,
          }}>{k}</button>
        ))}
      </div>
      {kind === 'objects' && <ObjectCrud ws={selectedWorkspace} />}
      {kind === 'links' && <LinkCrud ws={selectedWorkspace} />}
      {kind === 'actions' && <ActionCrud ws={selectedWorkspace} />}
    </div>
  )
}

// ============ 通用 fetch hook ============

function useOntologyFetch(ws: string, kind: Kind) {
  const { token } = useAuth()
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reload = useCallback(() => {
    setLoading(true); setError(null)
    fetch(`/api/admin/customers/${ws}/ontology/${kind}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async r => {
        if (!r.ok) throw new Error(`${r.status}: ${(await r.json().catch(() => ({}))).detail || r.statusText}`)
        return r.json()
      })
      .then(d => setItems(d[kind] || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [ws, kind, token])
  useEffect(() => { reload() }, [reload])
  return { items, loading, error, reload, token }
}

// ============ Objects ============

const EMPTY_OBJECT = {
  id: '', label: '', label_zh: '', comment: '', storage_file: '',
  status: 'active', visibility: 'normal', edits_only_via_actions: false,
  read_roles: '', read_except: '', write_roles: '', write_except: '',
  properties: [] as any[],
}

function ObjectCrud({ ws }: { ws: string }) {
  const { items, loading, error, reload, token } = useOntologyFetch(ws, 'objects')
  const [editing, setEditing] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)

  async function save(body: any, isNew: boolean) {
    setSaving(true)
    const name = body.id
    const url = isNew
      ? `/api/admin/customers/${ws}/ontology/objects`
      : `/api/admin/customers/${ws}/ontology/objects/${name}`
    const method = isNew ? 'POST' : 'PUT'
    const r = await fetch(url, {
      method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    setSaving(false)
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      alert(`保存失败：${r.status} ${d.detail || r.statusText}`)
      return
    }
    setEditing(null)
    reload()
  }

  async function del(name: string) {
    if (!window.confirm(`删除 Object Type "${name}"？properties 子表会一并删除。`)) return
    const r = await fetch(`/api/admin/customers/${ws}/ontology/objects/${name}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      alert(`删除失败：${r.status} ${d.detail || r.statusText}`)
      return
    }
    reload()
  }

  if (loading) return <div style={{ padding: 12, color: '#666' }}>加载中...</div>
  if (error) return <div style={{ padding: 12, color: '#dc2626' }}>⚠️ {error}</div>

  return (
    <div>
      <button onClick={() => setEditing({ ...EMPTY_OBJECT })} style={btnNew}>+ 新建 Object</button>
      {editing && (
        <ObjectForm initial={editing} onSave={save} onCancel={() => setEditing(null)} saving={saving} isNew={!editing.id} />
      )}
      <div style={{ marginTop: 12 }}>
        {items.map((o: any) => (
          <div key={o.id} style={rowStyle}>
            <strong>{o.id}</strong> <span style={{ color: '#666' }}>{o.label_zh || o.label}</span>
            <span style={{ marginLeft: 8, fontSize: 11, color: '#999' }}>{o.properties?.length || 0} props</span>
            <span style={{ float: 'right' }}>
              <button onClick={() => setEditing(o)} style={btnEdit}>编辑</button>
              <button onClick={() => del(o.id)} style={btnDel}>删除</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ObjectForm({ initial, onSave, onCancel, saving, isNew }:
  { initial: any; onSave: (b: any, isNew: boolean) => void; onCancel: () => void; saving: boolean; isNew: boolean }) {
  const [f, setF] = useState<any>({ ...initial, properties: [...(initial.properties || [])] })
  const set = (k: string, v: any) => setF({ ...f, [k]: v })
  const setProp = (i: number, k: string, v: any) => {
    const props = [...f.properties]; props[i] = { ...props[i], [k]: v }; setF({ ...f, properties: props })
  }
  const addProp = () => setF({ ...f, properties: [...f.properties, { name: '', type: 'string', read_roles: '', read_except: '', write_roles: '', write_except: '' }] })
  const delProp = (i: number) => setF({ ...f, properties: f.properties.filter((_: any, j: number) => j !== i) })

  return (
    <div style={formBox}>
      <h3 style={{ marginTop: 0 }}>{isNew ? '新建' : '编辑'} Object Type</h3>
      <Row label="id (主键)" disabled={!isNew}>
        <input value={f.id} onChange={e => set('id', e.target.value)} style={input} disabled={!isNew} />
      </Row>
      <Row label="label"><input value={f.label} onChange={e => set('label', e.target.value)} style={input} /></Row>
      <Row label="label_zh"><input value={f.label_zh} onChange={e => set('label_zh', e.target.value)} style={input} /></Row>
      <Row label="comment"><input value={f.comment} onChange={e => set('comment', e.target.value)} style={input} /></Row>
      <Row label="storage_file"><input value={f.storage_file} onChange={e => set('storage_file', e.target.value)} style={input} /></Row>
      <Row label="status">
        <select value={f.status} onChange={e => set('status', e.target.value)} style={input}>
          <option value="active">active</option><option value="deprecated">deprecated</option>
        </select>
      </Row>
      <Row label="visibility">
        <select value={f.visibility} onChange={e => set('visibility', e.target.value)} style={input}>
          <option value="normal">normal</option><option value="hidden">hidden</option>
        </select>
      </Row>
      <Row label="edits_only_via_actions">
        <input type="checkbox" checked={!!f.edits_only_via_actions} onChange={e => set('edits_only_via_actions', e.target.checked)} />
      </Row>
      <Row label="read_roles"><input value={f.read_roles} onChange={e => set('read_roles', e.target.value)} style={input} /></Row>
      <Row label="read_except"><input value={f.read_except} onChange={e => set('read_except', e.target.value)} style={input} /></Row>
      <Row label="write_roles"><input value={f.write_roles} onChange={e => set('write_roles', e.target.value)} style={input} /></Row>
      <Row label="write_except"><input value={f.write_except} onChange={e => set('write_except', e.target.value)} style={input} /></Row>

      <h4>Properties</h4>
      {f.properties.map((p: any, i: number) => (
        <div key={i} style={{ marginBottom: 8, padding: 8, background: '#f9fafb', borderRadius: 4 }}>
          <input placeholder="name" value={p.name} onChange={e => setProp(i, 'name', e.target.value)} style={{ ...input, width: 120 }} />
          <input placeholder="type" value={p.type} onChange={e => setProp(i, 'type', e.target.value)} style={{ ...input, width: 140, marginLeft: 4 }} />
          <input placeholder="read_roles" value={p.read_roles} onChange={e => setProp(i, 'read_roles', e.target.value)} style={{ ...input, width: 140, marginLeft: 4 }} />
          <input placeholder="read_except" value={p.read_except} onChange={e => setProp(i, 'read_except', e.target.value)} style={{ ...input, width: 120, marginLeft: 4 }} />
          <input placeholder="write_roles" value={p.write_roles} onChange={e => setProp(i, 'write_roles', e.target.value)} style={{ ...input, width: 140, marginLeft: 4 }} />
          <input placeholder="write_except" value={p.write_except} onChange={e => setProp(i, 'write_except', e.target.value)} style={{ ...input, width: 120, marginLeft: 4 }} />
          <button onClick={() => delProp(i)} style={{ ...btnDel, marginLeft: 4 }}>−</button>
        </div>
      ))}
      <button onClick={addProp} style={btnNew}>+ 添加 Property</button>

      <div style={{ marginTop: 12 }}>
        <button onClick={() => onSave(f, isNew)} disabled={saving} style={btnSave}>{saving ? '保存中...' : '保存'}</button>
        <button onClick={onCancel} style={{ ...btnEdit, marginLeft: 8 }}>取消</button>
      </div>
    </div>
  )
}

// ============ Links ============

const EMPTY_LINK = { id: '', label: '', label_zh: '', comment: '', domain: '', range: '', via: '', use_roles: '', use_except: '' }

function LinkCrud({ ws }: { ws: string }) {
  const { items, loading, error, reload, token } = useOntologyFetch(ws, 'links')
  const [editing, setEditing] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)

  async function save(body: any, isNew: boolean) {
    setSaving(true)
    const url = isNew ? `/api/admin/customers/${ws}/ontology/links`
      : `/api/admin/customers/${ws}/ontology/links/${body.id}`
    const r = await fetch(url, {
      method: isNew ? 'POST' : 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    setSaving(false)
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail || r.statusText}`); return }
    setEditing(null); reload()
  }
  async function del(name: string) {
    if (!window.confirm(`删除 Link "${name}"？`)) return
    const r = await fetch(`/api/admin/customers/${ws}/ontology/links/${name}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail}`); return }
    reload()
  }

  if (loading) return <div style={{ padding: 12, color: '#666' }}>加载中...</div>
  if (error) return <div style={{ padding: 12, color: '#dc2626' }}>⚠️ {error}</div>
  return (
    <div>
      <button onClick={() => setEditing({ ...EMPTY_LINK })} style={btnNew}>+ 新建 Link</button>
      {editing && <SimpleForm initial={editing} fields={['id', 'label', 'label_zh', 'comment', 'domain', 'range', 'via', 'use_roles', 'use_except']}
        onSave={save} onCancel={() => setEditing(null)} saving={saving} isNew={!editing.id} />}
      <div style={{ marginTop: 12 }}>
        {items.map((l: any) => (
          <div key={l.id} style={rowStyle}>
            <strong>{l.id}</strong> <span style={{ color: '#666' }}>{l.domain} → {l.range}</span>
            <span style={{ float: 'right' }}>
              <button onClick={() => setEditing(l)} style={btnEdit}>编辑</button>
              <button onClick={() => del(l.id)} style={btnDel}>删除</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============ Actions ============

const EMPTY_ACTION = {
  api_name: '', display_name: '', description: '', status: 'active',
  target_object_type: '', edits_object_types: '', locator_field: '',
  parameters: '[]', submission_criteria: '{}', side_effects: '[]',
}

function ActionCrud({ ws }: { ws: string }) {
  const { items, loading, error, reload, token } = useOntologyFetch(ws, 'actions')
  const [editing, setEditing] = useState<any | null>(null)
  const [saving, setSaving] = useState(false)

  async function save(body: any, isNew: boolean) {
    setSaving(true)
    // edits_object_types 是逗号分隔字符串 → 数组；JSON 字段解析（解析失败给出明确提示）
    let parameters: any, submissionCriteria: any, sideEffects: any
    try {
      parameters = JSON.parse(body.parameters || '[]')
      submissionCriteria = JSON.parse(body.submission_criteria || '{}')
      sideEffects = JSON.parse(body.side_effects || '[]')
    } catch (e: any) {
      setSaving(false)
      alert(`JSON 解析失败（parameters / submission_criteria / side_effects 必须是合法 JSON）：${e?.message || e}`)
      return
    }
    const payload: any = {
      ...body,
      edits_object_types: typeof body.edits_object_types === 'string'
        ? body.edits_object_types.split(',').map((s: string) => s.trim()).filter(Boolean) : body.edits_object_types,
      parameters,
      submission_criteria: submissionCriteria,
      side_effects: sideEffects,
    }
    const url = isNew ? `/api/admin/customers/${ws}/ontology/actions`
      : `/api/admin/customers/${ws}/ontology/actions/${payload.api_name}`
    const r = await fetch(url, {
      method: isNew ? 'POST' : 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    setSaving(false)
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail || r.statusText}`); return }
    setEditing(null); reload()
  }
  async function del(apiName: string) {
    if (!window.confirm(`删除 Action "${apiName}"？`)) return
    const r = await fetch(`/api/admin/customers/${ws}/ontology/actions/${apiName}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) { const d = await r.json().catch(() => ({})); alert(`失败：${d.detail}`); return }
    reload()
  }

  if (loading) return <div style={{ padding: 12, color: '#666' }}>加载中...</div>
  if (error) return <div style={{ padding: 12, color: '#dc2626' }}>⚠️ {error}</div>
  return (
    <div>
      <button onClick={() => setEditing({ ...EMPTY_ACTION })} style={btnNew}>+ 新建 Action</button>
      {editing && <ActionForm initial={editing} onSave={save} onCancel={() => setEditing(null)} saving={saving} isNew={!editing.api_name} />}
      <div style={{ marginTop: 12 }}>
        {items.map((a: any) => (
          <div key={a.api_name} style={rowStyle}>
            <strong>{a.api_name}</strong> <span style={{ color: '#666' }}>{a.display_name} → {a.target_object_type}</span>
            <span style={{ float: 'right' }}>
              <button onClick={() => setEditing({
                ...a,
                edits_object_types: (a.edits_object_types || []).join(', '),
                parameters: JSON.stringify(a.parameters || [], null, 2),
                submission_criteria: JSON.stringify(a.submission_criteria || {}, null, 2),
                side_effects: JSON.stringify(a.side_effects || [], null, 2),
              })} style={btnEdit}>编辑</button>
              <button onClick={() => del(a.api_name)} style={btnDel}>删除</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ActionForm({ initial, onSave, onCancel, saving, isNew }: any) {
  const [f, setF] = useState<any>({ ...initial })
  const set = (k: string, v: any) => setF({ ...f, [k]: v })
  return (
    <div style={formBox}>
      <h3 style={{ marginTop: 0 }}>{isNew ? '新建' : '编辑'} Action</h3>
      <Row label="api_name (主键)" disabled={!isNew}>
        <input value={f.api_name} onChange={e => set('api_name', e.target.value)} style={input} disabled={!isNew} />
      </Row>
      <Row label="display_name"><input value={f.display_name} onChange={e => set('display_name', e.target.value)} style={input} /></Row>
      <Row label="description"><input value={f.description} onChange={e => set('description', e.target.value)} style={input} /></Row>
      <Row label="status">
        <select value={f.status} onChange={e => set('status', e.target.value)} style={input}>
          <option value="active">active</option><option value="deprecated">deprecated</option>
        </select>
      </Row>
      <Row label="target_object_type"><input value={f.target_object_type} onChange={e => set('target_object_type', e.target.value)} style={input} /></Row>
      <Row label="edits_object_types (逗号分隔)"><input value={f.edits_object_types} onChange={e => set('edits_object_types', e.target.value)} style={input} /></Row>
      <Row label="locator_field"><input value={f.locator_field} onChange={e => set('locator_field', e.target.value)} style={input} /></Row>
      <Row label="parameters (JSON)">
        <textarea value={f.parameters} onChange={e => set('parameters', e.target.value)} style={{ ...input, height: 80, fontFamily: 'monospace' }} />
      </Row>
      <Row label="submission_criteria (JSON)">
        <textarea value={f.submission_criteria} onChange={e => set('submission_criteria', e.target.value)} style={{ ...input, height: 80, fontFamily: 'monospace' }} />
      </Row>
      <Row label="side_effects (JSON)">
        <textarea value={f.side_effects} onChange={e => set('side_effects', e.target.value)} style={{ ...input, height: 80, fontFamily: 'monospace' }} />
      </Row>
      <div style={{ marginTop: 12 }}>
        <button onClick={() => onSave(f, isNew)} disabled={saving} style={btnSave}>{saving ? '保存中...' : '保存'}</button>
        <button onClick={onCancel} style={{ ...btnEdit, marginLeft: 8 }}>取消</button>
      </div>
    </div>
  )
}

// ============ 通用 Simple 表单（Link 用）============

function SimpleForm({ initial, fields, onSave, onCancel, saving, isNew }: any) {
  const [f, setF] = useState<any>({ ...initial })
  const set = (k: string, v: any) => setF({ ...f, [k]: v })
  const idField = fields[0]
  return (
    <div style={formBox}>
      <h3 style={{ marginTop: 0 }}>{isNew ? '新建' : '编辑'}</h3>
      {fields.map((k: string) => (
        <Row key={k} label={k} disabled={!isNew && k === idField}>
          <input value={f[k] || ''} onChange={e => set(k, e.target.value)} style={input}
            disabled={!isNew && k === idField} />
        </Row>
      ))}
      <div style={{ marginTop: 12 }}>
        <button onClick={() => onSave(f, isNew)} disabled={saving} style={btnSave}>{saving ? '保存中...' : '保存'}</button>
        <button onClick={onCancel} style={{ ...btnEdit, marginLeft: 8 }}>取消</button>
      </div>
    </div>
  )
}

// ============ 小组件 + 样式 ============

function Row({ label, children, disabled }: { label: string; children: React.ReactNode; disabled?: boolean }) {
  return (
    <div style={{ marginBottom: 6, display: 'flex', alignItems: 'center' }}>
      <label style={{ width: 200, color: disabled ? '#999' : '#374151', fontSize: 13 }}>{label}</label>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  )
}

const input: React.CSSProperties = {
  padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 4, width: '100%', fontSize: 13,
}
const formBox: React.CSSProperties = {
  marginTop: 12, padding: 16, background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6,
}
const rowStyle: React.CSSProperties = {
  padding: '10px 12px', background: '#fff', border: '1px solid #e5e7eb', borderRadius: 4, marginBottom: 4,
}
const btnNew: React.CSSProperties = {
  padding: '6px 14px', borderRadius: 6, border: '1px solid #16a34a', background: '#16a34a', color: '#fff', cursor: 'pointer', fontSize: 13,
}
const btnEdit: React.CSSProperties = {
  padding: '4px 10px', borderRadius: 4, border: '1px solid #d1d5db', background: '#fff', color: '#374151', cursor: 'pointer', fontSize: 12, marginLeft: 4,
}
const btnDel: React.CSSProperties = {
  padding: '4px 10px', borderRadius: 4, border: '1px solid #ef4444', background: '#fff', color: '#dc2626', cursor: 'pointer', fontSize: 12, marginLeft: 4,
}
const btnSave: React.CSSProperties = {
  padding: '6px 18px', borderRadius: 6, border: '1px solid #2563eb', background: '#2563eb', color: '#fff', cursor: 'pointer', fontSize: 13,
}
