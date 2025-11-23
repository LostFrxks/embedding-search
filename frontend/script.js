const apiBase = "http://127.0.0.1:8000"
const form = document.getElementById("search-form")
const queryInput = document.getElementById("query-input")
const clearBtn = document.getElementById("clear-btn")
const searchBtn = document.getElementById("search-btn")
const semanticToggle = document.getElementById("semantic-toggle")
const statusLine = document.getElementById("status-line")
const metaCount = document.getElementById("meta-count")
const metaMode = document.getElementById("meta-mode")
const resultsSection = document.getElementById("results-section")
const resultsQuery = document.getElementById("results-query")
const resultsCount = document.getElementById("results-count")
const resultsGrid = document.getElementById("results-grid")
const emptyState = document.getElementById("empty-state")

console.log("frontend loaded")
console.log("form =", form)

function setStatus(text, type) {
  if (!text) {
    statusLine.textContent = ""
    statusLine.className = "status"
    return
  }

  statusLine.innerHTML = ""

  const span = document.createElement("span")
  const dot = document.createElement("div")
  dot.className = "status-dot"
  span.appendChild(dot)

  const t = document.createElement("span")
  t.textContent = text
  span.appendChild(t)

  statusLine.appendChild(span)
  statusLine.className = "status"

  if (type === "loading") statusLine.classList.add("status-loading")
  if (type === "error") statusLine.classList.add("status-error")
}

function formatPrice(price) {
  if (price === null || price === undefined) return "Цена договорная"
  const p = Number(price)
  if (Number.isNaN(p)) return "Цена договорная"
  return p.toLocaleString("ru-RU") + " сом"
}

function renderResults(query, items) {
  console.log("renderResults", { query, count: items.length })

  resultsQuery.textContent = query || "—"
  resultsGrid.innerHTML = ""
  metaCount.textContent = "Результатов: " + items.length
  resultsCount.textContent = items.length + " шт."

  if (!items.length) {
    emptyState.classList.remove("hidden")
    resultsSection.classList.remove("hidden")
    return
  }

  emptyState.classList.add("hidden")
  resultsSection.classList.remove("hidden")

  for (const item of items) {
    const card = document.createElement("div")
    card.className = "ad-card"

    const chip = document.createElement("div")
    chip.className = "ad-chip"
    const chipDot = document.createElement("div")
    chipDot.className = "ad-chip-dot"
    chip.appendChild(chipDot)
    const chipText = document.createElement("span")
    if (typeof item.score === "number") {
      chipText.textContent = "score " + item.score.toFixed(3)
    } else {
      chipText.textContent = "локальный поиск"
    }
    chip.appendChild(chipText)

    const titleEl = document.createElement("div")
    titleEl.className = "ad-title"
    titleEl.textContent = item.title || "Без названия"

    const row = document.createElement("div")
    row.className = "ad-row"
    const priceEl = document.createElement("div")
    priceEl.className = "ad-price"
    priceEl.textContent = formatPrice(item.price)
    const cityEl = document.createElement("div")
    cityEl.className = "ad-city"
    cityEl.textContent = item.city || "Город не указан"
    row.appendChild(priceEl)
    row.appendChild(cityEl)

    const descEl = document.createElement("div")
    descEl.className = "ad-desc"
    descEl.textContent = item.description || "Нет описания"

    const footer = document.createElement("div")
    footer.className = "ad-footer"
    const link = document.createElement("a")
    link.className = "ad-link"
    link.href = item.url || "#"
    link.target = "_blank"
    link.rel = "noopener noreferrer"
    link.textContent = "Открыть на Lalafo"
    const meta = document.createElement("div")
    meta.className = "ad-meta"
    meta.textContent = "id " + item.id
    footer.appendChild(link)
    footer.appendChild(meta)

    card.appendChild(chip)
    card.appendChild(titleEl)
    card.appendChild(row)
    card.appendChild(descEl)
    card.appendChild(footer)

    resultsGrid.appendChild(card)
  }
}

async function runSearch(mode, query) {
  console.log("callBackend start", query, "mode:", mode)

  metaMode.textContent =
    mode === "semantic"
      ? "Режим: семантический поиск"
      : "Режим: локальный поиск по title"

  setStatus("Обновляем базу с Lalafo", "loading")

  try {
    const searchUrl = apiBase + "/search?q=" + encodeURIComponent(query)
    const searchRes = await fetch(searchUrl)
    if (!searchRes.ok) {
      console.warn("Ошибка /search:", searchRes.status)
    }
  } catch (e) {
    console.warn("Сетевая ошибка /search:", e)
  }

  setStatus("Строим выдачу по базе", "loading")

  let dataUrl
  if (mode === "semantic") {
    dataUrl = apiBase + "/ads/semantic_search?q=" + encodeURIComponent(query)
  } else {
    dataUrl = apiBase + "/ads/local_search?q=" + encodeURIComponent(query)
  }

  const started = performance.now()
  const res = await fetch(dataUrl)
  const elapsed = performance.now() - started

  if (!res.ok) {
    setStatus("Ошибка поиска в базе: " + res.status, "error")
    return
  }

  const json = await res.json()
  const items = Array.isArray(json) ? json : json.results || []

  const ms = Math.round(elapsed)
  setStatus("Готово за " + ms + " мс", "")
  renderResults(query, items)
}

async function handleSearch() {
  const query = queryInput.value.trim()
  if (!query) {
    setStatus("Введи запрос", "error")
    return
  }

  const mode = semanticToggle.checked ? "semantic" : "local"
  console.log("search click", { query, mode })

  searchBtn.disabled = true
  try {
    await runSearch(mode, query)
  } catch (err) {
    console.error("Ошибка в runSearch:", err)
    setStatus("Ошибка: " + (err.message || err), "error")
  } finally {
    searchBtn.disabled = false
  }
}

searchBtn.addEventListener("click", e => {
  e.preventDefault()
  handleSearch()
})

queryInput.addEventListener("keydown", e => {
  if (e.key === "Enter") {
    e.preventDefault()
    handleSearch()
  }
})

queryInput.addEventListener("input", () => {
  if (queryInput.value.trim()) {
    clearBtn.classList.add("visible")
  } else {
    clearBtn.classList.remove("visible")
  }
})

clearBtn.addEventListener("click", e => {
  e.preventDefault()
  queryInput.value = ""
  clearBtn.classList.remove("visible")
})

semanticToggle.addEventListener("change", () => {
  const mode = semanticToggle.checked
    ? "семантический поиск"
    : "локальный поиск по title"
  metaMode.textContent = "Режим: " + mode
})
