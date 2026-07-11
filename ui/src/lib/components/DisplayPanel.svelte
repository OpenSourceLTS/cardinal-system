<script>


  let { workflowSteps = [], spokenLang = 'bn' } = $props();
  let allSteps = $state([]);

  $effect(() => {
    if (workflowSteps.length) {
      allSteps = [...allSteps, ...workflowSteps];
    }
  });

  export function clearCanvas() {
    allSteps = [];
  }
</script>

<div id="display-panel">
  <div id="canvas">
    {#each allSteps as step}
      <div class="workflow-card">
        <div class="workflow-step" class:error={!step.success}>
          <span>{step.verb}({step.tool})@{step.target}</span>
          <span>{step.success ? step.value : step.error}</span>
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  #display-panel {
    flex: 1;
    background-color: var(--bg-dark);
    background-image: var(--display-bg);
    transition: background-color 0.3s;
  }
  #canvas {
    flex: 1;
    overflow-y: auto;
    padding: 30px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
  }
  .workflow-card {
    width: 100%;
    max-width: 600px;
    margin-bottom: 10px;
    background: var(--step-bg);
    border-left: 3px solid var(--accent-cyan);
    padding: 8px 12px;
    border-radius: 4px;
  }
  .workflow-step {
    display: flex;
    justify-content: space-between;
    font-family: monospace;
    font-size: 0.85rem;
  }
  .workflow-step.error { color: #ff4444; }
</style>
