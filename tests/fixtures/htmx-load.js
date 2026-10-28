(() => {
    function appendIncludedValues(url, selector) {
        document.querySelectorAll(selector).forEach((element) => {
            if (!(element instanceof HTMLFormElement)) {
                return;
            }
            new FormData(element).forEach((value, key) => url.searchParams.set(key, value));
        });
    }

    async function request(element) {
        const path = element.getAttribute("hx-get");
        if (!path) {
            return;
        }
        const url = new URL(path, window.location.origin);
        const include = element.getAttribute("hx-include");
        if (include) {
            appendIncludedValues(url, include);
        }
        const response = await fetch(url, { headers: { "HX-Request": "true" } });
        const target = document.querySelector(element.getAttribute("hx-target")) || element;
        const content = await response.text();
        if (element.getAttribute("hx-swap") === "outerHTML") {
            target.outerHTML = content;
            return;
        }
        target.innerHTML = content;
        activate(target);
    }

    function activate(root) {
        root.querySelectorAll('[hx-get][hx-trigger*="load"]').forEach(request);
    }

    document.addEventListener("DOMContentLoaded", () => activate(document));
    document.addEventListener("click", (event) => {
        const element = event.target.closest("[hx-get]");
        if (!element || element.getAttribute("hx-trigger")?.includes("keyup")) {
            return;
        }
        event.preventDefault();
        request(element);
    });
})();