/* LOOM&LEAF storefront interactions — vanilla JS, progressively enhanced. */
(function () {
  "use strict";

  const onReady = (fn) => {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  };

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  function showToast(message, variant = "info") {
    let stack = document.querySelector("[data-toast-stack]");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      stack.setAttribute("aria-live", "polite");
      stack.setAttribute("data-toast-stack", "");
      document.body.appendChild(stack);
    }
    const toast = document.createElement("div");
    toast.className = "store-toast store-toast--" + variant;
    toast.setAttribute("role", "status");
    toast.setAttribute("data-toast", "");
    toast.innerHTML =
      '<span class="store-toast__icon" aria-hidden="true"><i class="bi bi-info-circle"></i></span>' +
      "<p></p>" +
      '<button type="button" class="store-toast__close" data-toast-close aria-label="Dismiss notification"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
    toast.querySelector("p").textContent = message;
    stack.appendChild(toast);
    window.setTimeout(() => dismissToast(toast), 7000);
  }

  function dismissToast(toast) {
    if (!toast || toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 220);
  }

  function initToasts() {
    document.querySelectorAll("[data-toast]").forEach((toast) => {
      window.setTimeout(() => dismissToast(toast), 7000);
    });
    document.addEventListener("click", (event) => {
      const close = event.target.closest("[data-toast-close]");
      if (close) {
        dismissToast(close.closest("[data-toast]"));
      }
    });
  }

  function initHeader() {
    const header = document.getElementById("site-header");
    if (!header) return;
    const update = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    update();
    window.addEventListener("scroll", update, { passive: true });
  }

  function initSearch() {
    const toggle = document.querySelector("[data-search-toggle]");
    const panel = document.getElementById("search-panel");
    if (!toggle || !panel) return;
    const input = panel.querySelector("[data-search-input]");
    const close = panel.querySelector("[data-search-close]");

    const open = () => {
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      document.body.classList.add("search-open");
      if (input) window.setTimeout(() => input.focus(), 30);
    };
    const hide = () => {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      document.body.classList.remove("search-open");
    };

    toggle.addEventListener("click", () => (panel.hidden ? open() : hide()));
    if (close) close.addEventListener("click", hide);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !panel.hidden) {
        hide();
        toggle.focus();
      }
    });
  }

  function initQuantity() {
    document.querySelectorAll("[data-qty-stepper]").forEach((stepper) => {
      const input = stepper.querySelector("[data-qty-input]");
      if (!input) return;
      const clamp = (value) => {
        const min = parseInt(input.min, 10) || 1;
        const max = parseInt(input.max, 10) || 10;
        return Math.min(Math.max(value, min), max);
      };
      stepper.querySelector("[data-qty-minus]")?.addEventListener("click", () => {
        input.value = clamp((parseInt(input.value, 10) || 1) - 1);
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      stepper.querySelector("[data-qty-plus]")?.addEventListener("click", () => {
        input.value = clamp((parseInt(input.value, 10) || 1) + 1);
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      input.addEventListener("blur", () => {
        input.value = clamp(parseInt(input.value, 10) || 1);
      });
    });
  }

  function initProductVariants() {
    const form = document.querySelector("[data-pdp-form]");
    const dataEl = document.getElementById("variant-data");
    if (!form || !dataEl) return;

    let variants = [];
    try {
      variants = JSON.parse(dataEl.textContent);
    } catch (error) {
      return;
    }

    const sizeInputs = Array.from(form.querySelectorAll('input[name="size"]'));
    const colorInputs = Array.from(form.querySelectorAll('input[name="color"]'));
    const stockLine = form.querySelector("[data-stock-line]");
    const hint = form.querySelector("[data-size-hint]");
    const addButton = form.querySelector("[data-add-to-bag]");
    const qtyInput = form.querySelector("[data-qty-input]");
    const colorLabel = form.querySelector("[data-selected-color]");

    const checked = (inputs) => inputs.find((input) => input.checked) || null;

    function stockFor(size, color) {
      const match = variants.find((variant) => variant.size === size && variant.color === color);
      return match ? match.stock : 0;
    }

    function update() {
      const size = checked(sizeInputs)?.value;
      const color = checked(colorInputs)?.value;
      if (!size || !color) return;
      const stock = stockFor(size, color);

      if (colorLabel) {
        const colorInput = checked(colorInputs);
        const label = colorInput?.closest("label")?.querySelector(".color-swatch__name");
        colorLabel.textContent = label ? label.textContent : "";
      }

      sizeInputs.forEach((input) => {
        const available = stockFor(input.value, color) > 0;
        input.closest("label")?.classList.toggle("is-unavailable", !available);
      });
      colorInputs.forEach((input) => {
        const available = stockFor(size, input.value) > 0;
        input.closest("label")?.classList.toggle("is-unavailable", !available);
      });

      if (stockLine) {
        if (stock <= 0) {
          stockLine.textContent = "Sold out in this size and colour";
          stockLine.classList.add("is-out");
        } else if (stock <= 4) {
          stockLine.textContent = "Only " + stock + " left in this combination";
          stockLine.classList.remove("is-out");
        } else {
          stockLine.textContent = stock + " pieces available";
          stockLine.classList.remove("is-out");
        }
      }
      if (hint) {
        hint.textContent =
          stock > 0
            ? "Ships in 2–4 business days. Free returns within 7 days."
            : "This combination is unavailable. Try another size or colour.";
      }

      if (addButton) {
        addButton.disabled = stock <= 0;
        addButton.firstChild.textContent = stock <= 0 ? "Sold out " : "Add to bag ";
      }
      if (qtyInput) {
        qtyInput.max = String(Math.max(1, Math.min(stock, 10)));
        if (parseInt(qtyInput.value, 10) > parseInt(qtyInput.max, 10)) {
          qtyInput.value = qtyInput.max;
        }
      }
    }

    sizeInputs.forEach((input) => input.addEventListener("change", update));
    colorInputs.forEach((input) => input.addEventListener("change", update));
    update();
  }

  function initGallery() {
    const main = document.querySelector("[data-gallery-main]");
    const thumbs = document.querySelectorAll("[data-gallery-thumb]");
    if (!main || !thumbs.length) return;
    thumbs.forEach((thumb) => {
      thumb.addEventListener("click", () => {
        main.src = thumb.dataset.src;
        thumbs.forEach((item) => item.classList.remove("is-active"));
        thumb.classList.add("is-active");
      });
    });
  }

  function updateWishlistUI(count, saved) {
    document.querySelectorAll("[data-wishlist-count]").forEach((el) => {
      el.textContent = count;
      el.classList.toggle("is-zero", count === 0);
    });
  }

  function initWishlist() {
    document.querySelectorAll("[data-wishlist-form]").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("[data-wishlist-toggle]");
        if (!button) return;
        button.disabled = true;
        try {
          const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin",
          });
          if (response.status === 401) {
            const payload = await response.json();
            showToast(payload.error || "Sign in to save pieces.", "info");
            window.setTimeout(() => {
              window.location.href = payload.login_url || "/accounts/login/";
            }, 900);
            return;
          }
          if (!response.ok) throw new Error("Wishlist request failed");
          const payload = await response.json();
          button.classList.toggle("is-saved", payload.saved);
          button.setAttribute("aria-pressed", payload.saved ? "true" : "false");
          button.setAttribute(
            "aria-label",
            payload.saved ? "Remove from wishlist" : "Save to wishlist"
          );
          const icon = button.querySelector("i");
          if (icon) {
            icon.classList.toggle("bi-heart-fill", payload.saved);
            icon.classList.toggle("bi-heart", !payload.saved);
          }
          updateWishlistUI(payload.count, payload.saved);
          showToast(payload.saved ? "Saved to your wishlist." : "Removed from your wishlist.", "success");
        } catch (error) {
          showToast("We couldn't update your wishlist. Please try again.", "error");
        } finally {
          button.disabled = false;
        }
      });
    });
  }

  function initAutoSubmit() {
    document.querySelectorAll("[data-auto-submit]").forEach((select) => {
      select.addEventListener("change", () => select.form?.submit());
    });
  }

  function initConfirm() {
    document.querySelectorAll("form[data-confirm]").forEach((form) => {
      form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm)) event.preventDefault();
      });
    });
  }

  function initCheckoutGuard() {
    const form = document.querySelector(".checkout-layout");
    if (!form) return;
    form.addEventListener("submit", () => {
      const button = form.querySelector('button[type="submit"]');
      if (button) {
        button.disabled = true;
        button.textContent = "Placing order…";
      }
    });
  }

  onReady(() => {
    initToasts();
    initHeader();
    initSearch();
    initQuantity();
    initProductVariants();
    initGallery();
    initWishlist();
    initAutoSubmit();
    initConfirm();
    initCheckoutGuard();
  });

  window.LoomLeaf = { showToast, getCookie };
})();
