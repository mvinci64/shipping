// Nome del cookie di sessione per shipping-web. Login separato da quello
// del Portal (viscotta_session su app.viscotta.com): domini diversi, il
// browser non lo condividerebbe comunque tra spedizioni.viscotta.com e
// app.viscotta.com. Stesso nome per coerenza concettuale (stesso account,
// stessa tabella viscotta.sessions), non per condivisione del cookie.
export const AUTH_COOKIE_NAME = "viscotta_session";
