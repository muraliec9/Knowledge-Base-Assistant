const chat = document.querySelector('#chat');
const form = document.querySelector('#ask-form');
const input = document.querySelector('#question');
const history = [];
const escapeHtml = value => value.replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));

function addMessage(text, role, sources = []) {
  const item = document.createElement('article'); item.className = `message ${role}`;
  item.innerHTML = `<div>${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;
  const highConfidenceSources = sources.filter(source => source.score >= 0.75);
  if (highConfidenceSources.length) {
    const list = document.createElement('div'); list.className = 'sources';
    list.innerHTML = '<strong>Sources</strong>' + highConfidenceSources.map((s, i) => `<details><summary>[${i + 1}] ${escapeHtml(s.title)} <em>${Math.round(s.score * 100)}% match</em></summary><p>${escapeHtml(s.excerpt)}</p></details>`).join('');
    item.append(list);
  }
  chat.append(item); chat.scrollTop = chat.scrollHeight;
}

form.addEventListener('submit', async event => {
  event.preventDefault(); const question = input.value.trim(); if (!question) return;
  addMessage(question, 'user'); input.value = ''; const pending = document.createElement('article'); pending.className = 'message assistant pending'; pending.textContent = 'Searching the knowledge base…'; chat.append(pending);
  try { const res = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question, history})}); const data = await res.json(); pending.remove(); addMessage(data.answer, 'assistant', data.sources); history.push({role:'user', content:question}, {role:'assistant', content:data.answer}); }
  catch { pending.textContent = 'Unable to reach the knowledge service. Please try again.'; }
});
document.querySelector('#file').addEventListener('change', async event => { const file = event.target.files[0]; if (!file) return; const body = new FormData(); body.append('file', file); const result = document.querySelector('#upload-result'); result.textContent = ' Indexing…'; const response = await fetch('/api/documents', {method:'POST', body}); const data = await response.json(); result.textContent = response.ok ? ` ${data.chunks_indexed} passages indexed.` : ` ${data.detail}`; });
