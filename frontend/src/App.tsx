import React, { useState } from 'react'

const API_BASE = '/api/v1'

export default function App() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [token, setToken] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<any>(null)
  const [jobId, setJobId] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [isCancelling, setIsCancelling] = useState<boolean>(false)

  const login = async () => {
    setError('')
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      })
      if (!res.ok) throw new Error(`登录失败: ${res.status}`)
      const data = await res.json()
      setToken(data.access_token)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const upload = async () => {
    if (!file || !token) return
    setError('')
    setStatus({ status: 'pending', message: '已提交请求到后端，正在等待响应...' })
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_BASE}/jobs/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form
      })
      if (!res.ok) throw new Error(`上传失败: ${res.status}`)
      const data = await res.json()
      setJobId(data.job_id)
      pollStatus(data.job_id)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const pollStatus = (id: string) => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/jobs/status/${id}`)
        const data = await res.json()
        setStatus(data)
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'unknown' || data.status === 'cancelled') {
          clearInterval(timer)
        }
      } catch {
      }
    }, 2000)
  }

  const cancelJob = async () => {
    if (!jobId) return
    setError('')
    setIsCancelling(true)
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`, {
        method: 'DELETE',
        headers: token ? { 'Authorization': `Bearer ${token}` } : undefined
      })
      const data = await res.json()
      setStatus((prev: any) => ({ ...(prev || {}), ...data }))
    } catch (e: any) {
      setError(e.message || '取消任务失败')
    } finally {
      setIsCancelling(false)
    }
  }

  const openResult = async () => {
    if (!status?.report_url || !token) return
    // fetch JSON result and show in new window
    const res = await fetch(status.report_url, { headers: { 'Authorization': `Bearer ${token}` } })
    const data = await res.json()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl p-6 space-y-6">
        <h1 className="text-2xl font-bold">Test Report Agent · 前端控制台</h1>

        <section className="space-y-3 rounded-xl border border-slate-800 p-4 bg-slate-900/60">
          <p className="text-sm text-slate-300">登录以获取访问令牌（JWT）。</p>
          <div className="flex gap-3">
            <input className="px-3 py-2 rounded bg-slate-800 border border-slate-700" placeholder="用户名" value={username} onChange={e => setUsername(e.target.value)} />
            <input className="px-3 py-2 rounded bg-slate-800 border border-slate-700" placeholder="密码" type="password" value={password} onChange={e => setPassword(e.target.value)} />
            <button className="px-3 py-2 rounded bg-sky-500 text-slate-950 font-semibold" onClick={login}>登录</button>
          </div>
          {token && <p className="text-xs text-emerald-300">已获得令牌</p>}
        </section>

        <section className="space-y-3 rounded-xl border border-slate-800 p-4 bg-slate-900/60">
          <p className="text-sm text-slate-300">上传测试结果 Excel，后端将执行分析流水线并生成 JSON 结果。</p>
          <input type="file" accept=".xlsx" onChange={e => setFile(e.target.files?.[0] || null)} />
          <button disabled={!file || !token} className="px-3 py-2 rounded bg-violet-500 text-slate-950 font-semibold disabled:opacity-50" onClick={upload}>上传并启动分析</button>
          {error && <p className="text-xs text-rose-300">{error}</p>}
        </section>

        <section className="space-y-3 rounded-xl border border-slate-800 p-4 bg-slate-900/60">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-slate-300">任务状态</p>
            <div className="flex items-center gap-3">
              {status?.status && (
                <span className="px-2 py-1 text-xs rounded-full border border-slate-700 bg-slate-900 text-slate-200">
                  当前状态: {status.status}
                </span>
              )}
              {jobId && (status?.status === 'pending' || status?.status === 'running' || status?.status === 'cancelling') && (
                <button
                  onClick={cancelJob}
                  disabled={isCancelling}
                  className="px-3 py-2 rounded bg-rose-500 hover:bg-rose-400 text-slate-950 font-semibold text-xs disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isCancelling ? '正在取消…' : '紧急停止当前任务'}
                </button>
              )}
            </div>
          </div>
          <pre className="text-xs bg-slate-950 p-3 rounded border border-slate-800">{JSON.stringify(status || {}, null, 2)}</pre>
          {status?.report_url && status?.status === 'completed' && (
            <button className="px-3 py-2 rounded bg-emerald-500 text-slate-950 font-semibold" onClick={openResult}>
              查看分析结果（JSON）
            </button>
          )}
        </section>
      </div>
    </div>
  )
}
