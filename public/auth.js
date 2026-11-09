function loginDestination() {
  const value=new URLSearchParams(location.search).get("next");
  if(!value || !value.startsWith("/") || value.startsWith("//") || /[\\\x00-\x1f]/.test(value)) return "/";
  const target=new URL(value,location.origin);
  return target.origin===location.origin && target.pathname==="/" ? target.pathname+target.search : "/";
}
const form = document.querySelector("#auth-form");
let token = null;
function configureInvite() {
  const candidate = new URLSearchParams(location.hash.slice(1)).get("invite");
  if (!candidate) return;
  token = candidate;
  history.replaceState(null, "", "/login");
  document.querySelector("#auth-title").textContent = "Seu lugar na equipe.";
  document.querySelector("#auth-description").textContent =
    "Defina seu nome e senha para ativar ou recuperar seu acesso.";
  document.querySelector("#name-label").hidden = false;
  form.elements.name.required = true;
  document.querySelector("#email-label").hidden = true;
  form.elements.email.required = false;
  form.elements.password.autocomplete = "new-password";
  form.elements.password.minLength = 12;
  document.querySelector("#password-help").hidden = false;
  document.querySelector("#auth-submit").textContent = "Ativar meu acesso";
}
configureInvite();
window.addEventListener("hashchange", configureInvite);
form.onsubmit = async (e) => {
  e.preventDefault();
  const button = document.querySelector("#auth-submit");
  button.disabled = true;
  document.querySelector("#auth-error").textContent = "";
  try {
    const fields = Object.fromEntries(new FormData(form));
    const response = await fetch(token ? "/api/accept-invite" : "/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...fields, token }),
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.error || "Não foi possível entrar.");
    location.replace(loginDestination());
  } catch (error) {
    document.querySelector("#auth-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
