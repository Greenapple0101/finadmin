// 별도 프런트 프레임워크 없이 ITSM API를 연결합니다. innerHTML로 사용자 입력을 넣지 않습니다.
// 로그인 → 업무 신원 조회 → 요청 목록 → 선택한 요청의 처리 순서로 읽으면 됩니다.
let itsmActor = null;
let itsmPage = 0;
let itsmHasNext = false;
let itsmSelected = null;
let itsmBusy = false;
const stateNames = { REQUESTED: "접수됨", APPROVED: "승인됨", COMPLETED: "처리 완료" };
const $ = selector => document.querySelector(selector);

function node(tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  return element;
}
function announce(text, error = false) {
  $("#itsm-message").textContent = text;
  $("#itsm-message").className = error ? "error-message" : "success-message";
}
function buttons() {
  document.querySelectorAll("#itsm-workspace button").forEach(button => { button.disabled = itsmBusy; });
  $("#itsm-refresh").disabled = itsmBusy || !itsmActor;
  $("#itsm-prev").disabled = itsmBusy || itsmPage === 0;
  $("#itsm-next").disabled = itsmBusy || !itsmHasNext;
}
async function task(work) {
  if (itsmBusy) return; // 빠르게 두 번 눌러 같은 생성 요청을 보내지 않도록 돕습니다. 서버 멱등키는 별도 과제입니다.
  itsmBusy = true; buttons();
  try { await work(); }
  catch (error) { announce(error.message || "요청을 처리하지 못했습니다.", true); }
  finally { itsmBusy = false; buttons(); }
}
function hideDetail() {
  itsmSelected = null;
  $("#itsm-detail").hidden = true;
  $("#itsm-complete").hidden = true;
}
async function loadItsm() {
  itsmActor = await itsmApi("/me");
  const role = itsmActor.operator ? "처리 담당자 · 승인 가능" : itsmActor.reviewer ? "승인자" : "요청 직원";
  $("#itsm-profile").textContent = `${itsmActor.companyName} · ${itsmActor.displayName} · ${role}`;
  $("#itsm-list-heading").textContent = itsmActor.reviewer || itsmActor.operator ? "우리 회사 요청 목록" : "내 요청 목록";
  $("#itsm-workspace").hidden = false;
  itsmPage = 0; hideDetail();
  await refreshRequests();
}
async function refreshRequests() {
  const page = await itsmApi(`/requests?page=${itsmPage}`);
  itsmHasNext = page.hasNext;
  $("#itsm-page-label").textContent = `${page.page + 1}페이지 · 최대 20건`;
  const container = $("#itsm-list"); container.replaceChildren();
  if (!page.items.length) container.append(node("p", "아직 요청이 없습니다. 필요한 서비스를 등록해 보세요.", "empty-state"));
  for (const request of page.items) {
    const card = node("article", "", "request-card");
    const heading = node("div", "", "section-heading");
    heading.append(node("h4", request.serviceName), node("span", stateNames[request.status], "status-badge " + request.status.toLowerCase()));
    card.append(heading, node("p", `등록 ${new Date(request.createdAt).toLocaleString("ko-KR")} · ${request.requesterId === itsmActor.userId ? "본인 요청" : "회사 직원 요청"}`, "hint"));
    const detail = node("button", "상세 보기", "secondary");
    detail.addEventListener("click", () => task(() => showRequest(request.id)));
    card.append(detail); container.append(card);
  }
  $("#itsm-summary").hidden = !itsmActor.operator;
  if (itsmActor.operator) {
    const summary = await itsmApi("/summary");
    const area = $("#itsm-summary"); area.replaceChildren();
    for (const [label, value] of [["승인 대기", summary.requested], ["처리 대기", summary.approved], ["처리 완료", summary.completed]]) {
      const card = node("div", "", "summary-card"); card.append(node("span", label), node("strong", String(value))); area.append(card);
    }
  }
}
async function showRequest(id) {
  // 목록의 버튼 표시를 우회하더라도 이 상세 조회는 서버에서 소속·요청자를 다시 검사합니다.
  const request = await itsmApi(`/requests/${id}`); itsmSelected = request;
  const area = $("#itsm-detail"); area.replaceChildren(); area.hidden = false;
  area.append(node("h3", request.serviceName), node("p", stateNames[request.status], "status-badge"), node("p", request.reason, "request-reason"));
  const history = node("dl", "", "request-history");
  for (const [label, value] of [["요청 ID", request.id], ["요청자", request.requesterId],
      ["승인자", request.approverId], ["승인 시각", request.approvedAt && new Date(request.approvedAt).toLocaleString("ko-KR")],
      ["완료 처리자", request.completedBy], ["완료 시각", request.completedAt && new Date(request.completedAt).toLocaleString("ko-KR")]]) {
    if (value) history.append(node("dt", label), node("dd", value));
  }
  area.append(history);
  if (request.completionNote) area.append(node("h4", "처리 결과"), node("p", request.completionNote, "request-reason"));
  if (request.status === "REQUESTED" && itsmActor.reviewer) {
    if (request.requesterId === itsmActor.userId) area.append(node("p", "본인 요청은 다른 승인자가 승인해야 합니다.", "hint"));
    else {
      const approve = node("button", "요청 승인");
      approve.addEventListener("click", () => task(async () => {
        await itsmApi(`/requests/${request.id}/approve`, "POST");
        await refreshRequests(); await showRequest(request.id); announce("승인했습니다. 처리 담당자가 완료할 수 있습니다.");
      }));
      area.append(approve);
    }
  }
  $("#itsm-complete").hidden = !(itsmActor.operator && request.status === "APPROVED");
  $("#completion-note").value = "";
  area.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
$("#itsm-create").addEventListener("submit", event => {
  event.preventDefault();
  task(async () => {
    const request = await itsmApi("/requests", "POST", { serviceName: $("#service-name").value, reason: $("#service-reason").value });
    $("#itsm-create").reset(); itsmPage = 0;
    await refreshRequests(); await showRequest(request.id); announce("요청을 등록했습니다. 승인자의 확인을 기다려 주세요.");
  });
});
$("#itsm-complete").addEventListener("submit", event => {
  event.preventDefault();
  task(async () => {
    if (!itsmSelected) return;
    const id = itsmSelected.id;
    await itsmApi(`/requests/${id}/complete`, "POST", { note: $("#completion-note").value });
    await refreshRequests(); await showRequest(id); announce("처리 결과를 저장하고 완료했습니다.");
  });
});
$("#itsm-refresh").addEventListener("click", () => task(async () => { hideDetail(); await refreshRequests(); announce("현재 요청 목록을 불러왔습니다."); }));
$("#itsm-prev").addEventListener("click", () => task(async () => { itsmPage--; hideDetail(); await refreshRequests(); }));
$("#itsm-next").addEventListener("click", () => task(async () => { itsmPage++; hideDetail(); await refreshRequests(); }));
document.addEventListener("finlab-login", () => task(loadItsm));
document.addEventListener("finlab-expired", () => {
  itsmActor = null; hideDetail(); $("#itsm-workspace").hidden = true;
  $("#itsm-profile").textContent = "다시 로그인하면 요청을 이어서 확인할 수 있습니다.";
  buttons();
});
