import fetch from "node-fetch";

// 오늘 날짜의 '일간' 지표를 요청합니다.
async function getDailyMetrics() {
  const date = new Date().toISOString().slice(0, 10);
  const localStart = new Date(`${date}T00:00:00`).getTime();
  
  console.log("--- [Daily Metrics] ---");
  const res = await fetch(`http://localhost:4000/metrics/daily?dayStart=${localStart}`, {
    // ⭐️ API 키를 실제 사용하는 키로 수정했습니다.
    headers: { "x-api-key": "PHQ9123" }
  });
  console.log(await res.json());
}

// 이번 주 '주간' 지표를 요청합니다.
async function getWeeklyMetrics() {
  console.log("\n--- [Weekly Metrics] ---");
  const res = await fetch(`http://localhost:4000/metrics/weekly`, {
    headers: { "x-api-key": "PHQ9123" }
  });
  console.log(await res.json());
}

// 실행
getDailyMetrics();
getWeeklyMetrics();