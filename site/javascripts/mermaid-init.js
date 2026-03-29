window.mermaidConfig = {
  startOnLoad: false,
  securityLevel: "loose",
  theme: "default"
}

function renderMermaid() {
  if (!window.mermaid) return
  window.mermaid.initialize(window.mermaidConfig)
  const blocks = document.querySelectorAll("pre code.mermaid")
  blocks.forEach((block, index) => {
    const parent = block.parentElement
    if (!parent) return
    const graphDefinition = block.textContent || ""
    const wrapperId = `mermaid-${index}-${Date.now()}`
    const container = document.createElement("div")
    container.className = "mermaid"
    container.id = wrapperId
    container.textContent = graphDefinition
    parent.replaceWith(container)
  })
  window.mermaid.run({ querySelector: ".mermaid" })
}

if (document$ && typeof document$.subscribe === "function") {
  document$.subscribe(() => renderMermaid())
} else {
  window.addEventListener("load", renderMermaid)
}
