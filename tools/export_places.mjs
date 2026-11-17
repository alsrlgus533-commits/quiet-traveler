// index.html 안의 장소 데이터(PLACES, API_NAME, SWAPS, FAMOUS, FAMOUS_PHOTO, PHOTO, STAY, RAIN_FIT, SUN_UP, SUN_DOWN)를
// 에이전트가 쓰는 agent/data/places.json 으로 뽑는다. 화면과 에이전트가 같은 값을 쓰게 하려고, 장소를 고친 뒤엔 이걸 다시 돌린다.
//   node tools/export_places.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(root, "index.html"), "utf8");

function grab(name) {
  const m = new RegExp(`const ${name}\\s*=`).exec(html);
  if (!m) throw new Error(`${name} not found`);
  const start = m.index;
  let i = html.indexOf("=", start) + 1, depth = 0, inStr = null;
  for (; i < html.length; i++) {
    const c = html[i];
    if (inStr) { if (c === "\\") { i++; continue; } if (c === inStr) inStr = null; continue; }
    if (c === '"' || c === "'" || c === "`") { inStr = c; continue; }
    if ("[{(".includes(c)) depth++;
    else if ("]})".includes(c)) depth--;
    else if (c === ";" && depth === 0) break;
  }
  const expr = html.slice(html.indexOf("=", start) + 1, i);
  return Function(`"use strict"; return (${expr});`)();
}

const out = {
  places: grab("PLACES"),
  api_name: grab("API_NAME"),
  swaps: grab("SWAPS"),
  famous: grab("FAMOUS"),
  famous_photo: grab("FAMOUS_PHOTO"),
  photo: [...grab("PHOTO")],
  stay: grab("STAY"),
  rain_fit: grab("RAIN_FIT"),
  sun_up: grab("SUN_UP"),
  sun_down: grab("SUN_DOWN"),
};
const dir = join(root, "agent", "data");
mkdirSync(dir, { recursive: true });
writeFileSync(join(dir, "places.json"), JSON.stringify(out, null, 1), "utf8");
console.log(`saved places=${out.places.length} famous=${out.famous.length}`);
