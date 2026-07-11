<script>
  let { sender = 'user', content = '', translated = '', timing = 0 } = $props();
  const now = new Date();
  const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  let name = $derived(sender === 'user' ? 'You' : sender === 'ai' ? 'Cardinal' : 'System');
  let color = $derived(sender === 'user' ? 'var(--accent-blue)' : 'var(--accent-cyan)');
</script>

<div class="message {sender}">
  <div class="msg-header">
    <span class="msg-name" style="color: {color}">{name}</span>
    <span class="msg-time">{time}</span>
  </div>
  <div class="msg-content">{content}</div>
  {#if translated && translated !== content}
    <div class="msg-translated">
      → {translated}
      {#if timing}
        <span class="msg-timing">({timing}s)</span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .message {
    max-width: 85%;
    padding: 10px 15px;
    border-radius: 12px;
    font-size: 0.9rem;
    line-height: 1.4;
  }
  .message.user {
    align-self: flex-end;
    background-color: var(--accent-blue);
    color: var(--msg-user-text);
    border-bottom-right-radius: 2px;
  }
  .message.ai {
    align-self: flex-start;
    background-color: var(--bg-panel-light);
    border: 1px solid var(--msg-ai-border);
    color: var(--text-main);
    border-bottom-left-radius: 2px;
  }
  .message.system {
    align-self: center;
    background: transparent;
    color: var(--text-dim);
    font-size: 0.75rem;
    font-style: italic;
    border: 1px dashed var(--text-dim);
    border-radius: 4px;
  }
  .msg-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
    font-size: 0.75rem;
  }
  .msg-name { font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
  .msg-time { opacity: 0.7; font-size: 0.7rem; }
  .msg-content { word-wrap: break-word; }
  .msg-translated {
    color: var(--text-dim);
    font-size: 0.8rem;
    border-top: 1px solid var(--text-dim);
    margin-top: 4px;
    padding-top: 4px;
  }
  .msg-timing { opacity: 0.6; }
</style>
