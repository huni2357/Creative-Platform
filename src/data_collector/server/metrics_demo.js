
import fetch from "node-fetch";

const date = process.argv[2] || new Date().toISOString().slice(0,10);
const localStart = new Date(`${date}T00:00:00`).getTime();

const res = await fetch(`http://localhost:4000/metrics/daily?dayStart=${localStart}`, {
  headers: { "x-api-key": "CHANGE_ME_SECURE_KEY" }
});
console.log(await res.json());
