/**
 * agent_bridge_http.js — 统一 DSH agent 的 HTTP 端点插件（可加载进任意 DSH profile）。
 *
 * 在 DSH 里注册 `POST /api/agent/message`，按 peer（渠道级用户标识）创建/复用
 * 一个持久 DSH agent，把消息喂给真实 agent 运行时并返回最终回复。
 * 这样 Telegram(Python 桥) 与 QQ(官方插件) 可以共用同一套 agent 运行时、
 * 模型与持久化 —— 只要它们位于同一个 DSH profile/进程。
 *
 * 作为 ESM Corda 插件使用：把本文件放进某个 profile 的 patch（cordis.patch.yml），
 * 或直接在 dsh-plugin 组合里以本地路径加载。兼容 host（不需 harness 动态 API）。
 */
export const name = 'agent-bridge-http';
export const inject = ['agents', 'sessions', 'agentDefaultModel', 'webServer'];

export const apply = async (ctx) => {
  const agents = ctx.agents;
  const sessions = ctx.sessions;
  const agentDefaultModel = ctx.agentDefaultModel;
  const webServer = ctx.webServer;

  // 解析工作目录（失败则忽略 cwd，让 DSH 用默认）
  let cwd;
  const sandbox = ctx.get('sandboxPolicy');
  if (sandbox && typeof sandbox.workspaceRoot === 'string' && sandbox.workspaceRoot) {
    cwd = sandbox.workspaceRoot;
  }

  /** peer -> AgentHandle（内存中常驻，按 peer 分会话） */
  const handles = new Map();
  /** peer -> 串行 turn 队列（避免同会话并发重入） */
  const queue = new Map();

  const readBody = (req) =>
    new Promise((resolve, reject) => {
      let data = '';
      req.on('data', (c) => { data += c; });
      req.on('end', () => resolve(data));
      req.on('error', reject);
    });

  const newMessageId = () =>
    'm-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);

  const makeUserMessage = (text) => ({
    id: newMessageId(),
    role: 'user',
    content: [{ type: 'text', text: String(text) }],
    source: { kind: 'user' }
  });

  const summarizeAgent = (agent, firstSeq) => {
    let started = false;
    let text = '';
    let reason = null;
    for (const event of agent.session.events) {
      if (event.seq < firstSeq) continue;
      if (event.type === 'turn/start') { started = true; continue; }
      if (!started) continue;
      if (event.type === 'assistant/message') {
        const content = (event.data && event.data.message && event.data.message.content) || [];
        let joined = '';
        for (const b of content) {
          if (b && b.type === 'text' && typeof b.text === 'string') joined += b.text;
        }
        if (joined !== '') text = joined;
      }
      if (event.type === 'turn/end') reason = event.data ? event.data.reason : null;
    }
    return { text, reason };
  };

  const sanitize = (id) =>
    String(id == null ? 'anon' : id).replace(/[^a-zA-Z0-9-_.@]/g, '_').slice(0, 64);

  const getOrCreate = async (peerId) => {
    const existing = handles.get(peerId);
    if (existing) return existing;
    const selection = agentDefaultModel.currentSelection();
    const agentId = 'bridge-' + peerId + '-' + Date.now().toString(36);
    const meta = {};
    if (cwd) meta.cwd = cwd;
    const handle = await agents.create({
      sessionId: agentId,
      meta,
      agentOptions: {
        provider: selection && selection.provider,
        model: selection && selection.model
      }
    });
    await handle.agent.whenIdle();
    handles.set(peerId, handle);
    return handle;
  };

  const send = (res, code, obj) => {
    res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(obj));
  };

  const route = webServer.register({
    kind: 'exact',
    path: '/api/agent/message',
    handler: async (req, res) => {
      try {
        if (req.method !== 'POST') { send(res, 405, { ok: false, error: 'method not allowed' }); return; }
        let payload = {};
        try { payload = JSON.parse((await readBody(req)) || '{}'); }
        catch (e) { send(res, 400, { ok: false, error: 'bad json' }); return; }
        const peerId = sanitize(payload.peer);
        const text = String(payload.message != null ? payload.message : (payload.text != null ? payload.text : '')).trim();
        if (!text) { send(res, 400, { ok: false, error: 'empty message' }); return; }

        const prev = queue.get(peerId) || Promise.resolve();
        const run = prev.then(async () => {
          const handle = await getOrCreate(peerId);
          const firstSeq = handle.agent.session.seq;
          handle.agent.followup(makeUserMessage(text));
          await handle.agent.whenIdle();
          await sessions.flush(handle.agent.session);
          return summarizeAgent(handle.agent, firstSeq);
        });
        queue.set(peerId, run.catch(() => {}));
        const result = await run;
        send(res, 200, { ok: true, peer: peerId, reply: result.text, reason: result.reason });
      } catch (err) {
        console.error('[agent-bridge-http] error:', err && err.message ? err.message : String(err));
        send(res, 500, { ok: false, error: String(err && err.message ? err.message : err) });
      }
    }
  });

  return () => {
    try { route(); } catch (e) { /* ignore */ }
    for (const h of handles.values()) h.dispose().catch(() => {});
    handles.clear();
  };
};