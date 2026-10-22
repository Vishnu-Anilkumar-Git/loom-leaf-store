/* Razorpay test-mode checkout. Payment state is only ever confirmed by the server. */
(function () {
  "use strict";

  const dataEl = document.getElementById("payment-data");
  const payButton = document.querySelector("[data-razorpay-pay]");
  const statusEl = document.querySelector("[data-payment-status]");
  if (!dataEl || !payButton) return;

  let config;
  try {
    config = JSON.parse(dataEl.textContent);
  } catch (error) {
    return;
  }

  function csrfToken() {
    const match = document.cookie.match(/(^|;\s*)csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[2]) : "";
  }

  function setStatus(message, isError = false) {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.classList.toggle("is-error", isError);
  }

  async function notifyServer(url) {
    try {
      await fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
    } catch (error) {
      /* The order simply remains pending if this call fails. */
    }
  }

  async function verifyPayment(response) {
    setStatus("Verifying payment…");
    const body = new FormData();
    body.append("razorpay_order_id", response.razorpay_order_id || config.order_id);
    body.append("razorpay_payment_id", response.razorpay_payment_id || "");
    body.append("razorpay_signature", response.razorpay_signature || "");

    try {
      const result = await fetch(config.verify_url, {
        method: "POST",
        body,
        headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      const payload = await result.json();
      if (!result.ok || !payload.ok) {
        setStatus(payload.error || "Payment could not be verified.", true);
        payButton.disabled = false;
        return;
      }
      setStatus("Payment verified. Redirecting to your order…");
      window.location.href = payload.redirect || config.return_url;
    } catch (error) {
      setStatus("We could not reach the payment verification endpoint. Please check your order page before retrying.", true);
      payButton.disabled = false;
    }
  }

  payButton.addEventListener("click", () => {
    if (typeof window.Razorpay === "undefined") {
      setStatus("The payment SDK could not load. Check your connection and reload this page.", true);
      return;
    }
    payButton.disabled = true;

    const checkout = new window.Razorpay({
      key: config.key,
      order_id: config.order_id,
      amount: config.amount,
      currency: config.currency,
      name: "LOOM&LEAF",
      description: config.description,
      prefill: config.prefill,
      theme: { color: "#111111" },
      handler: verifyPayment,
      modal: {
        ondismiss: () => {
          setStatus("Payment window closed. Your order remains pending.", true);
          payButton.disabled = false;
          notifyServer(config.cancelled_url);
        },
      },
    });

    checkout.on("payment.failed", (response) => {
      const description =
        response?.error?.description || "The payment failed. No order status was changed.";
      setStatus(description, true);
      payButton.disabled = false;
    });

    checkout.open();
  });
})();
