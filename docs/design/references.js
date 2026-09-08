// Standalone design references: no API, uploads, model calls or stored user data.
const tabs = [...document.querySelectorAll('[role="tab"]')];
function selectTab(tab) {
  tabs.forEach((item) => {
    const selected = item === tab;
    item.setAttribute("aria-selected", String(selected));
    item.tabIndex = selected ? 0 : -1;
    document.getElementById(item.dataset.panel).hidden = !selected;
  });
}
tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", (event) => {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft")
      next = (index + tabs.length - 1) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next === undefined) return;
    event.preventDefault();
    selectTab(tabs[next]);
    tabs[next].focus();
  });
});
const sourceLabels = {
  deadline: "Выделен фрагмент о сроке подачи заявки",
  budget: "Выделен фрагмент о начальной цене контракта",
  delivery: "Выделен фрагмент о сроке поставки",
};
document.querySelectorAll("[data-source]").forEach((button) => {
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".pdf-quote")
      .forEach((quote) => quote.classList.remove("highlighted"));
    const source = document.getElementById(button.dataset.source);
    source.classList.add("highlighted");
    document.querySelector(".citation-caption").textContent =
      `↳ ${sourceLabels[button.dataset.source]}`;
    source.scrollIntoView({ behavior: "instant", block: "nearest" });
  });
});
