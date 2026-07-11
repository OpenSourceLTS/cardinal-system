<script>
  import Message from './Message.svelte';
  import { loadSessions, createSession, deleteSession, loadHistory, sendChat, loadPreferences } from '../api.js';
  import * as Select from '$lib/components/ui/select';
  import { Mic, SendHorizontal, Sun, Moon, Plus, Trash2 } from '@lucide/svelte';

  let { messages = [], onSend, toggleTheme, theme = 'light' } = $props();

  let sessions = $state([]);
  let currentSessionId = $state(localStorage.getItem('cardinal_session') || '');
  let spokenLang = $state('bn');
  let inputText = $state('');
  let isSending = $state(false);
  let voiceModeActive = $state(false);
  let isSpeaking = $state(false);
  let recognition = null;

  async function init() {
    sessions = await loadSessions();
    if (!currentSessionId) {
      await createNewSession();
    } else if (sessions.some(s => s.id === currentSessionId)) {
      const raw = await loadHistory(currentSessionId);
      messages = raw.filter(e => e.role !== 'tool').map(e => ({
        role: e.role,
        content: e.role === 'user' ? (e.user_original || e.content) : e.content,
        translated: e.role === 'user' ? e.content : (e.translated_response || '')
      }));
    } else {
      await createNewSession();
    }
    const prefs = await loadPreferences();
    if (prefs.spoken_lang) spokenLang = prefs.spoken_lang;
  }

  async function createNewSession() {
    const sid = await createSession();
    currentSessionId = sid;
    localStorage.setItem('cardinal_session', sid);
    messages = [];
    sessions = await loadSessions();
  }

  async function deleteCurrentSession() {
    if (!currentSessionId || !confirm(`Delete session ${currentSessionId.slice(0, 8)}...?`)) return;
    await deleteSession(currentSessionId);
    currentSessionId = '';
    localStorage.removeItem('cardinal_session');
    messages = [];
    sessions = await loadSessions();
    if (sessions.length) {
      currentSessionId = sessions[0].id;
      localStorage.setItem('cardinal_session', currentSessionId);
      messages = await loadHistory(currentSessionId);
    } else {
      await createNewSession();
    }
  }

  async function switchSession(sessionId) {
    currentSessionId = sessionId;
    localStorage.setItem('cardinal_session', sessionId);
    messages = await loadHistory(sessionId);
  }

  let switching = $state(false);
  $effect(() => {
    if (switching) {
      const sid = currentSessionId;
      switching = false;
      if (sid) switchSession(sid);
    }
  });

  async function handleSend(text) {
    if (isSending || !text?.trim()) return;
    isSending = true;
    messages = [...messages, { role: 'user', content: text, translated: '' }];
    inputText = '';

    const data = await sendChat(text, currentSessionId);
    if (data.user_translated) {
      messages[messages.length - 1] = { ...messages[messages.length - 1], translated: data.user_translated };
    }
    const respText = data.response || '';
    const translatedResp = data.translated_response || '';

    const aiMsg = { role: 'assistant', content: respText, translated: translatedResp };
    messages = [...messages, aiMsg];
    onSend?.(aiMsg, spokenLang);
    isSending = false;
  }

  function sttLang(code) {
    const map = { bn: 'bn-BD', zh: 'zh-CN', zt: 'zh-TW', nb: 'nb-NO' };
    return map[code] || code + '-' + code.toUpperCase();
  }

  let sttErrorRetries = 0;
  function initSTT() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    if (recognition) try { recognition.stop(); } catch {}
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = sttLang(spokenLang);

    let finalTranscript = '';
    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += t + ' ';
        else interim += t;
      }
      inputText = finalTranscript + interim;
      if (finalTranscript.trim()) {
        clearTimeout(window.sendTimeout);
        window.sendTimeout = setTimeout(() => {
          if (inputText.trim()) {
            const text = finalTranscript;
            finalTranscript = '';
            handleSend(text);
          }
        }, 1200);
      }
    };

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'aborted') return;
      sttErrorRetries++;
      const delay = event.error === 'no-speech' ? 2000 : 500;
      if (sttErrorRetries < 5) {
        setTimeout(() => { if (voiceModeActive && !isSpeaking) try { recognition.start(); } catch {} }, delay);
      } else {
        voiceModeActive = false;
      }
    };

    recognition.onend = () => {
      if (voiceModeActive && !isSpeaking) try { recognition.start(); } catch {}
    };
  }

  function toggleVoice() {
    voiceModeActive = !voiceModeActive;
    if (voiceModeActive) {
      sttErrorRetries = 0;
      initSTT();
      try { recognition?.start(); } catch {}
    } else {
      if (recognition) try { recognition.stop(); } catch {}
    }
  }

  export function pauseSTT() {
    if (recognition && voiceModeActive) try { recognition.stop(); } catch {}
  }
  export function resumeSTT() {
    if (recognition && voiceModeActive && !isSpeaking) try { recognition.start(); } catch {}
  }
  export function markSpeaking(v) { isSpeaking = v; }

  $effect(() => { init(); });
</script>

<div id="chat-panel">
  <div class="panel-header">
    <div class="header-left">
      <h1>Cardinal</h1>
      <div class="session-controls">
        <Select.Root bind:value={currentSessionId} onValueChange={(v) => switchSession(v)}>
          <Select.Trigger class="session-select-trigger">
            <span data-slot="select-value">{currentSessionId ? currentSessionId.slice(0, 8) : 'Session'}</span>
          </Select.Trigger>
          <Select.Content class="session-select-content">
            {#each sessions as s}
              <Select.Item value={s.id}>{s.id.slice(0, 8)} — {s.preview ? s.preview.slice(0, 40) : '(empty)'}</Select.Item>
            {/each}
          </Select.Content>
        </Select.Root>
        <button class="btn-icon" onclick={createNewSession} title="New session"><Plus size={14} /></button>
        <button class="btn-icon danger" onclick={deleteCurrentSession} title="Delete session"><Trash2 size={14} /></button>
      </div>
    </div>
    <div id="status-indicators">
      <button class="btn-icon theme-btn" onclick={toggleTheme} title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
        {#if theme === 'dark'}
          <Sun size={16} />
        {:else}
          <Moon size={16} />
        {/if}
      </button>
      <span class="indicator {voiceModeActive ? 'active' : 'offline'}">Voice: {voiceModeActive ? 'On' : 'Off'}</span>
    </div>
  </div>

  <div id="chat-history">
    {#each messages as msg}
      <Message sender={msg.role} content={msg.content} translated={msg.translated} />
    {/each}
  </div>

  <div id="chat-input-area">
    <input type="text" id="user-input" bind:value={inputText} placeholder="Click anywhere or type to start..."
      onkeypress={(e) => e.key === 'Enter' && handleSend(inputText)} />
    <button id="mic-btn" class={voiceModeActive ? 'listening' : ''} onclick={toggleVoice} title={voiceModeActive ? 'Stop voice input' : 'Start voice input'}><Mic size={18} /></button>
    <button id="send-btn" onclick={() => handleSend(inputText)} disabled={isSending} title="Send message"><SendHorizontal size={18} /></button>
  </div>
</div>

<style>
  #chat-panel {
    width: 40%;
    min-width: 350px;
    background-color: var(--bg-panel);
    border-left: 1px solid var(--border-glow);
    display: flex;
    flex-direction: column;
    box-shadow: 5px 0 15px rgba(0, 0, 0, 0.1);
    transition: background-color 0.3s, border-color 0.3s;
  }
  .panel-header {
    padding: 15px 20px;
    border-bottom: 1px solid var(--border-glow);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--panel-header-bg);
  }
  .header-left { display: flex; align-items: center; gap: 15px; }
  h1 {
    font-size: 1.2rem;
    font-weight: 300;
    letter-spacing: 3px;
    color: var(--accent-cyan);
    text-transform: uppercase;
  }
  .session-controls { display: flex; gap: 5px; align-items: center; }

  :global(.session-select-trigger) {
    max-width: 200px;
    height: 28px;
    font-size: 0.75rem;
  }
  :global(.session-select-content) {
    background: var(--bg-panel);
    border: 1px solid var(--border-glow);
    border-radius: 4px;
    z-index: 50;
    min-width: 200px;
  }
  .btn-icon {
    display: flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; padding: 0;
    background: transparent; border: 1px solid var(--text-dim);
    color: var(--text-dim); border-radius: 4px; cursor: pointer;
    transition: all 0.3s;
  }
  .btn-icon:hover { border-color: var(--accent-cyan); color: var(--accent-cyan); }
  .btn-icon.danger:hover { border-color: #ff4444; color: #ff4444; }
  .theme-btn { width: 30px; height: 28px; }

  #status-indicators { display: flex; gap: 10px; font-size: 0.75rem; align-items: center; }
  .indicator {
    padding: 4px 8px;
    border: 1px solid var(--text-dim);
    border-radius: 4px;
    color: var(--text-dim);
    transition: all 0.3s;
  }
  .indicator.active {
    border-color: var(--accent-cyan);
    color: var(--accent-cyan);
    box-shadow: 0 0 8px var(--accent-cyan);
  }
  .indicator.offline { border-color: var(--text-dim); color: var(--text-dim); }

  #chat-history {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 15px;
  }

  #chat-input-area {
    padding: 15px;
    display: flex;
    gap: 10px;
    border-top: 1px solid var(--border-glow);
    background-color: var(--bg-panel-light);
    transition: background-color 0.3s, border-color 0.3s;
  }
  #user-input {
    flex: 1;
    background: var(--bg-dark);
    border: 1px solid var(--text-dim);
    border-radius: 4px;
    padding: 10px 15px;
    color: var(--text-main);
    font-size: 1rem;
    outline: none;
    transition: border-color 0.3s;
  }
  #user-input:focus { border-color: var(--accent-cyan); box-shadow: 0 0 8px var(--input-focus-shadow); }
  #chat-input-area button {
    display: flex; align-items: center; justify-content: center;
    width: 40px; height: 40px; padding: 0;
    background: transparent;
    border: 1px solid var(--text-dim);
    color: var(--text-dim);
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    transition: all 0.3s;
  }
  #chat-input-area button:hover { border-color: var(--accent-cyan); color: var(--accent-cyan); }
  #chat-input-area button:disabled { opacity: 0.4; cursor: default; }

  #mic-btn.listening {
    border-color: var(--accent-warning);
    color: var(--accent-warning);
    box-shadow: 0 0 10px var(--accent-warning);
    animation: pulse 1.5s infinite;
  }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(255, 170, 0, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(255, 170, 0, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 170, 0, 0); }
  }
  input:focus, button:focus-visible { outline: 2px solid var(--accent-cyan); outline-offset: 2px; }
</style>
