<script>
  import ChatPanel from '$lib/components/ChatPanel.svelte';
  import DisplayPanel from '$lib/components/DisplayPanel.svelte';
  import { loadPreferences, ttsUrl } from '$lib/api.js';

  let messages = $state([]);
  let workflowSteps = $state([]);
  let spokenLang = $state('bn');
  let chatPanelRef;
  let displayPanelRef;

  let theme = $state(localStorage.getItem('cardinal_theme') || 'light');

  $effect(() => {
    document.documentElement.setAttribute('data-theme', theme === 'dark' ? 'dark cerberus' : 'cerberus');
    localStorage.setItem('cardinal_theme', theme);
  });

  function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark';
  }

  let ttsAudioContext = null;

  function initAudio() {
    ttsAudioContext = new (window.AudioContext || window.webkitAudioContext)();
  }

  function speakText(text, lang) {
    if (!text) return;
    const l = (lang || spokenLang).split('-')[0];
    const url = ttsUrl(text, l);
    chatPanelRef?.pauseSTT?.();
    chatPanelRef?.markSpeaking?.(true);

    const audio = new Audio(url);
    audio.onended = () => {
      chatPanelRef?.markSpeaking?.(false);
      chatPanelRef?.resumeSTT?.();
    };
    audio.onerror = () => {
      chatPanelRef?.markSpeaking?.(false);
      chatPanelRef?.resumeSTT?.();
    };
    audio.play().catch(() => {
      chatPanelRef?.markSpeaking?.(false);
      chatPanelRef?.resumeSTT?.();
    });
  }

  function handleSend(aiMsg, lang) {
    const text = aiMsg.translated || aiMsg.content;
    if (text) speakText(text, lang);
  }

  function firstClickStart() {
    document.removeEventListener('click', firstClickStart, true);
    document.removeEventListener('touchstart', firstClickStart, true);
    initAudio();
  }

  $effect(() => {
    document.addEventListener('click', firstClickStart, true);
    document.addEventListener('touchstart', firstClickStart, true);
  });

  $effect(() => {
    loadPreferences().then(prefs => {
      if (prefs.spoken_lang) spokenLang = prefs.spoken_lang;
    });
  });
</script>

<div id="app-container">
  <DisplayPanel bind:this={displayPanelRef} {workflowSteps} {spokenLang} />
  <ChatPanel bind:this={chatPanelRef} {messages} onSend={handleSend} {toggleTheme} {theme} />
</div>

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: var(--bg-dark);
    color: var(--text-main);
    overflow: hidden;
    height: 100vh;
    transition: background-color 0.3s, color 0.3s;
  }
  :global(::-webkit-scrollbar) { width: 6px; }
  :global(::-webkit-scrollbar-track) { background: var(--bg-dark); }
  :global(::-webkit-scrollbar-thumb) { background: var(--text-dim); border-radius: 3px; }
  :global(::-webkit-scrollbar-thumb:hover) { background: var(--accent-cyan); }

  #app-container {
    display: flex;
    height: 100vh;
    width: 100vw;
  }
</style>
