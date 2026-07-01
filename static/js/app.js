const SAMPLE_SNIPPETS = {
    print: `for i in xrange(3):
    print i`,
    dict: `def emit_values(payload):
    if payload.has_key("alpha"):
        for key, value in payload.iteritems():
            print key, value`,
    input: `def normalize_name(name):
    if isinstance(name, basestring):
        return unicode(name).strip()
    return raw_input("fallback: ")`,
};

const state = {
    originalCode: "",
    newCode: "",
    candidateCode: "",
    diff: "",
    candidateDiff: "",
    report: "",
    runId: "",
    analysis: null,
    suggestions: [],
    critiques: [],
    plan: null,
    validation: null,
    ml: null,
    logs: [],
    rolledBack: false,
    outputAvailable: false,
};

const codeInput = document.getElementById("codeInput");
const lineNumbers = document.getElementById("lineNumbers");
const reviewPanel = document.getElementById("reviewPanel");
const diffPanel = document.getElementById("diffPanel");
const outputPanel = document.getElementById("outputPanel");
const reportPanel = document.getElementById("reportPanel");
const terminal = document.getElementById("terminal");
const runHistory = document.getElementById("runHistory");
const mlSummary = document.getElementById("mlSummary");
const mlBadge = document.getElementById("mlBadge");
const focusText = document.getElementById("focusText");
const modeBadge = document.getElementById("modeBadge");
const statusBadge = document.getElementById("statusBadge");
const summaryStrip = document.getElementById("summaryStrip");
const summarySource = document.getElementById("summarySource");
const summaryIssues = document.getElementById("summaryIssues");
const summaryChanges = document.getElementById("summaryChanges");
const summaryState = document.getElementById("summaryState");
const advancedPanel = document.getElementById("advancedPanel");
const advancedToggleBtn = document.getElementById("advancedToggleBtn");
const advancedToggleLabel = document.getElementById("advancedToggleLabel");
const runBtn = document.getElementById("runBtn");
const actionHint = document.getElementById("actionHint");
const downloadReport = document.getElementById("downloadReport");
const downloadOutput = document.getElementById("downloadOutput");
const downloadOutputTop = document.getElementById("downloadOutputTop");
const copyDiffBtn = document.getElementById("copyDiffBtn");
const copyOutputBtn = document.getElementById("copyOutputBtn");
const uploadBtn = document.getElementById("uploadBtn");
const fileInput = document.getElementById("fileInput");

const tabs = {
    review: document.getElementById("reviewTab"),
    diff: document.getElementById("diffTab"),
    output: document.getElementById("outputTab"),
    report: document.getElementById("reportTab"),
};

const panels = {
    review: reviewPanel,
    diff: diffPanel,
    output: outputPanel,
    report: reportPanel,
};

const steps = {
    analyze: document.getElementById("stepAnalyze"),
    review: document.getElementById("stepReview"),
    modernize: document.getElementById("stepModernize"),
    validate: document.getElementById("stepValidate"),
};

document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    resetUi();
    fetchModelStatus();
    loadRunHistory();
});

function bindEvents() {
    codeInput.addEventListener("input", updateLineNumbers);
    codeInput.addEventListener("scroll", syncScroll);

    document.querySelectorAll(".sampleBtn").forEach((button) => {
        button.addEventListener("click", () => {
            const sample = SAMPLE_SNIPPETS[button.dataset.sample];
            if (!sample) {
                return;
            }
            codeInput.value = sample;
            updateLineNumbers();
            syncScroll();
            showToast("Sample loaded", "success");
        });
    });

    document.addEventListener("keydown", (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            runBtn.click();
        }
    });

    Object.entries(tabs).forEach(([key, button]) => {
        button.addEventListener("click", () => activateTab(key));
    });

    Object.entries(steps).forEach(([key, button]) => {
        button.addEventListener("click", () => handleStepNavigation(key));
    });

    advancedToggleBtn.addEventListener("click", () => setAdvancedOpen(advancedPanel.classList.contains("hidden")));
    runHistory.addEventListener("click", handleRunHistoryClick);
    runBtn.addEventListener("click", handlePrimaryAction);
    copyDiffBtn.addEventListener("click", () => copyPanelContent("diff"));
    copyOutputBtn.addEventListener("click", () => copyPanelContent("output"));
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener("click", () => fileInput.click());
        fileInput.addEventListener("change", handleFileUpload);
    }
}

async function handlePrimaryAction() {
    const action = state.primaryAction || "analyze";
    if (action === "analyze") {
        await handleAnalyze();
        return;
    }
    if (action === "modernize") {
        await handleModernize();
        return;
    }
    if (action === "apply") {
        applyOutputToEditor();
    }
}

async function handleAnalyze() {
    const code = codeInput.value;
    if (!code.trim()) {
        showToast("Paste legacy Python before analyzing", "error");
        return;
    }
    const maxLines = Number(codeInput.dataset.maxLines || 0);
    const maxChars = Number(codeInput.dataset.maxChars || 0);
    const lineCount = code.split("\n").length;
    if (maxLines && lineCount > maxLines) {
        showToast(`Input too large: limit is ${maxLines} lines`, "error");
        return;
    }
    if (maxChars && code.length > maxChars) {
        showToast(`Input too large: limit is ${maxChars} characters`, "error");
        return;
    }

    state.originalCode = code;
    state.newCode = "";
    state.candidateCode = "";
    state.diff = "";
    state.candidateDiff = "";
    state.report = "";
    state.runId = "";
    state.validation = null;
    state.logs = [];
    state.rolledBack = false;
    state.outputAvailable = false;

    resetUi(false);
    setStepState("analyze");
    setFocus("Analyzing your code to find legacy patterns and decide what can be modernized automatically.");
    setStatus("Analyzing");
    setPrimaryAction("working");
    log("Starting analysis...", "system");

    try {
        const response = await fetch("/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code }),
        });
        const data = await response.json();

        if (!response.ok || !data.analysis?.success) {
            throw new Error(data.detail || data.analysis?.error || "Analysis failed.");
        }

        state.analysis = data.analysis;
        state.suggestions = data.suggestions || [];
        state.critiques = data.critiques?.critiques || [];
        state.plan = data.plan || { selected_plans: [] };
        state.ml = data.ml_reasoner || state.ml;

        log(`Detected source profile: ${state.analysis.probable_source_version}`, "analyzer");
        log(`Found ${state.analysis.legacy_issues?.length || 0} legacy issues.`, "analyzer");
        log(`${(state.plan.selected_plans || []).length} modernization changes are ready to run.`, "system");

        renderSummary();
        renderReview();
        renderMlSummary(state.ml);
        activateTab("review");

        if (state.analysis.mode === "BLOCKED") {
            setMode("Blocked");
            setStatus("Blocked");
            setStepState("review", ["analyze"]);
            setFocus("Analysis found risky constructs that block automatic modernization. Review the issues before making changes.");
            setPrimaryAction("blocked");
            showToast("Automatic modernization is blocked for this code", "error");
            return;
        }

        setMode(state.analysis.mode || "Safe");
        setStatus((state.plan.selected_plans || []).length ? "Ready To Modernize" : "Review Findings");
        setStepState("review", ["analyze"]);
        setFocus(
            (state.plan.selected_plans || []).length
                ? "Review the findings on the right, then click Modernize Code to generate the updated result."
                : "Analysis is complete. Review the findings on the right. No automatic modernization changes are ready yet."
        );
        setPrimaryAction((state.plan.selected_plans || []).length ? "modernize" : "analyze");
        showToast("Analysis complete", "success");
    } catch (error) {
        setMode("Error");
        setStatus("Analysis Failed");
        setFocus("Analysis failed. Check the advanced log and try again.");
        setPrimaryAction("analyze");
        log(error.message || "Analysis failed.", "error");
        showToast("Analysis failed", "error");
    }
}

async function handleModernize() {
    const code = codeInput.value;
    const maxLines = Number(codeInput.dataset.maxLines || 0);
    const maxChars = Number(codeInput.dataset.maxChars || 0);
    const lineCount = code.split("\n").length;
    if (maxLines && lineCount > maxLines) {
        showToast(`Input too large: limit is ${maxLines} lines`, "error");
        return;
    }
    if (maxChars && code.length > maxChars) {
        showToast(`Input too large: limit is ${maxChars} characters`, "error");
        return;
    }
    state.originalCode = code;
    setStepState("modernize", ["analyze", "review"]);
    setStatus("Modernizing");
    setFocus("Running the guarded modernization pipeline. The editor will stay unchanged until you choose to apply the result.");
    setPrimaryAction("working");
    log("Running modernization pipeline...", "system");

    try {
        const response = await fetch("/refactor", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code }),
        });
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.detail || data.error || "Modernization failed.");
        }

        state.runId = data.run_id || "";
        state.analysis = data.analysis || state.analysis;
        state.suggestions = data.suggestions || state.suggestions;
        state.plan = data.plan || state.plan;
        state.validation = data.validation || null;
        state.newCode = data.new_code || "";
        state.candidateCode = data.candidate_code || "";
        state.diff = data.diff || "";
        state.candidateDiff = data.candidate_diff || "";
        state.report = data.report || "";
        state.ml = data.ml_reasoner || state.ml;
        state.logs = data.logs || [];
        state.rolledBack = Boolean(data.rolled_back);
        state.outputAvailable = Boolean(data.output_available && state.validation?.success && state.newCode);

        renderSummary();
        renderReview();
        renderDiff();
        renderOutput();
        renderReport();
        renderLogs();
        renderMlSummary(state.ml);
        activateTab(state.diff || state.candidateDiff ? "diff" : "output");

        updateOutputDownload();
        if (state.report) {
            const blob = new Blob([state.report], { type: "text/markdown" });
            downloadReport.href = URL.createObjectURL(blob);
            downloadReport.classList.remove("hidden");
        }

        setStepState("validate", ["analyze", "review", "modernize"]);
        setMode(state.analysis?.mode || "Safe");
        setStatus(state.validation?.success ? "Validated" : (state.rolledBack ? "Rolled Back" : "No Safe Output"));
        setFocus(
            state.validation?.success
                ? "Modernization finished. Review the diff, then apply the updated code if you want to continue editing it."
                : "Modernization did not produce a safe output. Review the validation error and fix the source before downloading anything."
        );
        setPrimaryAction(state.outputAvailable && state.newCode !== state.originalCode ? "apply" : "analyze");

        if (state.runId) {
            log(`Saved run ${state.runId}.`, "success");
            loadRunHistory();
        }

        showToast(state.validation?.success ? "Modernization completed" : "No safe output produced", state.validation?.success ? "success" : "error");
    } catch (error) {
        setMode("Error");
        setStatus("Modernization Failed");
        setFocus("Modernization failed. Check the advanced log and try again.");
        setPrimaryAction("modernize");
        log(error.message || "Modernization failed.", "error");
        showToast("Modernization failed", "error");
    }
}

function applyOutputToEditor() {
    if (!state.newCode) {
        return;
    }
    codeInput.value = state.newCode;
    updateLineNumbers();
    syncScroll();
    setPrimaryAction("analyze");
    setFocus("Changes were applied to the editor. You can analyze again or continue editing.");
    showToast("Updated code applied to editor", "success");
}

function handleFileUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
        return;
    }
    const maxLines = Number(codeInput.dataset.maxLines || 0);
    const maxChars = Number(codeInput.dataset.maxChars || 0);

    const reader = new FileReader();
    reader.onload = () => {
        const content = String(reader.result || "");
        const lineCount = content.split("\n").length;
        if (maxLines && lineCount > maxLines) {
            showToast(`File too large: limit is ${maxLines} lines`, "error");
            return;
        }
        if (maxChars && content.length > maxChars) {
            showToast(`File too large: limit is ${maxChars} characters`, "error");
            return;
        }
        codeInput.value = content;
        updateLineNumbers();
        syncScroll();
        showToast(`Loaded ${file.name}`, "success");
        event.target.value = "";
    };
    reader.onerror = () => {
        showToast("Failed to read file", "error");
    };
    reader.readAsText(file);
}

function handleStepNavigation(step) {
    if (step === "analyze") {
        codeInput.focus();
        codeInput.scrollIntoView({ behavior: "smooth", block: "center" });
        showToast("Editor focused", "info");
        return;
    }

    if (step === "review") {
        if (!state.analysis) {
            showToast("Analyze the code first", "error");
            return;
        }
        activateTab("review");
        showToast("Review opened", "success");
        return;
    }

    if (step === "modernize") {
        if (!state.analysis) {
            showToast("Analyze the code first", "error");
            return;
        }
        activateTab("review");
        runBtn.scrollIntoView({ behavior: "smooth", block: "center" });
        runBtn.focus();
        showToast(state.primaryAction === "modernize" ? "Ready to modernize" : "Review the findings, then continue", "success");
        return;
    }

    if (step === "validate") {
        if (!state.diff && !state.report && !state.newCode) {
            showToast("Run modernization to review the result", "error");
            return;
        }
        const targetTab = state.diff ? "diff" : (state.newCode ? "output" : "report");
        activateTab(targetTab);
        showToast("Validation view opened", "success");
    }
}

async function fetchModelStatus() {
    try {
        const response = await fetch("/model-status");
        const data = await response.json();
        state.ml = data;
        renderMlSummary(data);
    } catch (error) {
        renderMlSummary(null);
    }
}

async function loadRunHistory() {
    try {
        const response = await fetch("/runs?limit=6");
        const data = await response.json();
        const runs = data.runs || [];

        if (!runs.length) {
            runHistory.innerHTML = `<div class="rounded-xl border border-dashed border-white/10 bg-black/20 p-3 text-xs text-zinc-500">No saved runs yet.</div>`;
            return;
        }

        runHistory.innerHTML = runs.map((run) => `
            <button data-run-id="${escapeHtml(run.run_id)}" class="w-full rounded-xl border border-white/5 bg-black/20 p-3 text-left transition-colors hover:border-orange-500/20 hover:bg-black/30">
                <div class="flex items-center justify-between gap-3">
                    <div class="font-mono text-[11px] text-zinc-300">${escapeHtml(run.run_id.slice(0, 8))}</div>
                    <span class="text-[10px] uppercase tracking-[0.18em] ${run.validation_success ? "text-emerald-400" : "text-amber-400"}">${run.validation_success ? "Validated" : "Review"}</span>
                </div>
                <div class="mt-2 text-[11px] text-zinc-400">${escapeHtml(run.probable_source_version || "Unknown source")}</div>
            </button>
        `).join("");
    } catch (error) {
        runHistory.innerHTML = `<div class="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-200">Failed to load run history.</div>`;
    }
}

async function handleRunHistoryClick(event) {
    const target = event.target.closest("[data-run-id]");
    if (!target) {
        return;
    }

    try {
        const response = await fetch(`/runs/${target.dataset.runId}`);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Run not found.");
        }

        state.runId = data.run_id || "";
        state.originalCode = data.original_code || "";
        state.newCode = data.new_code || "";
        state.candidateCode = data.candidate_code || "";
        state.analysis = data.analysis || null;
        state.validation = data.validation || null;
        state.diff = data.diff || "";
        state.candidateDiff = data.candidate_diff || "";
        state.report = data.report || "";
        state.rolledBack = Boolean(data.rolled_back);
        state.outputAvailable = Boolean(data.output_available && state.validation?.success && state.newCode);
        state.logs = [
            `Loaded saved run ${state.runId}.`,
            `Validation status: ${data.validation_success ? "validated" : "needs review"}.`,
        ];
        state.plan = {
            selected_plans: (data.applied_transformations || []).map((id) => ({ suggestion: { id } })),
        };

        renderSummary();
        renderReview();
        renderDiff();
        renderOutput();
        renderReport();
        renderLogs();
        updateOutputDownload();
        setAdvancedOpen(true);
        activateTab(state.diff ? "diff" : "report");
        setStepState("validate", ["analyze", "review", "modernize"]);
        setMode(state.analysis?.mode || "Review");
        setStatus(data.validation_success ? "Validated" : "Needs Review");
        setFocus("Saved run loaded. Review the diff, output, or report without changing the editor.");
        setPrimaryAction(state.outputAvailable && state.newCode !== state.originalCode ? "apply" : "analyze");
        showToast("Saved run loaded", "success");
    } catch (error) {
        showToast(error.message || "Failed to load saved run", "error");
    }
}

function renderSummary() {
    if (!state.analysis) {
        summaryStrip.classList.add("hidden");
        return;
    }

    summaryStrip.classList.remove("hidden");
    summarySource.textContent = state.analysis.probable_source_version || "Unknown";
    summaryIssues.textContent = String(state.analysis.legacy_issues?.length || 0);
    summaryChanges.textContent = String(state.plan?.selected_plans?.length || 0);
    summaryState.textContent = state.validation
        ? (state.validation.success ? "Validated" : "Review")
        : ((state.plan?.selected_plans?.length || 0) ? "Ready" : "Waiting");
}

function renderReview() {
    if (!state.analysis) {
        renderPanelPlaceholder(
            reviewPanel,
            "Analysis results will appear here",
            "Start with Analyze Code to detect legacy syntax, compatibility risks, and available modernization steps.",
            "Load a sample or paste Python 2 style code into the editor."
        );
        return;
    }

    const issues = state.analysis.legacy_issues || [];
    const plans = state.plan?.selected_plans || [];
    const warnings = [
        ...(state.analysis.semantic_risks || []).map((risk) => risk.message),
        ...(state.validation?.warnings || []),
        ...(state.validation && !state.validation.success ? [state.validation.error || state.validation.message || "Validation failed."] : []),
    ];
    const riskTone = riskToneClasses(state.analysis.risk_score);

    reviewPanel.innerHTML = `
        <div class="panel-shell space-y-4">
            <div class="rounded-2xl border border-white/10 bg-black/20 p-5">
                <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                        <div class="text-lg font-semibold text-white">${escapeHtml(state.analysis.probable_source_version || "Unknown source")}</div>
                        <div class="mt-2 text-sm text-zinc-400">${issues.length} legacy issue${issues.length === 1 ? "" : "s"} found · ${plans.length} change${plans.length === 1 ? "" : "s"} ready to run</div>
                    </div>
                    <span class="inline-flex rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${riskTone}">${escapeHtml(state.analysis.risk_score || "Low")}</span>
                </div>
            </div>

            <div class="grid gap-4 lg:grid-cols-2">
                <div class="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <div class="text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">What We Found</div>
                    <div class="mt-3 space-y-2">
                        ${issues.length
                            ? issues.slice(0, 5).map((issue) => `
                                <div class="rounded-xl border border-white/5 bg-black/30 px-3 py-3">
                                    <div class="text-sm text-zinc-200">${escapeHtml(issue.message)}</div>
                                    <div class="mt-1 text-[11px] text-zinc-500">Line ${issue.line}</div>
                                </div>
                            `).join("")
                            : `<div class="text-sm text-zinc-500">No legacy issues were detected.</div>`}
                    </div>
                </div>

                <div class="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <div class="text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500">What Will Change</div>
                    <div class="mt-3 space-y-2">
                        ${plans.length
                            ? plans.map((item, index) => `
                                <div class="rounded-xl border border-white/5 bg-black/30 px-3 py-3">
                                    <div class="text-sm text-zinc-200">${index + 1}. ${escapeHtml(item.suggestion?.reasoning || item.suggestion?.id || "Modernization change")}</div>
                                </div>
                            `).join("")
                            : `<div class="text-sm text-zinc-500">No automatic changes are ready. You can still review the findings and decide manually.</div>`}
                    </div>
                </div>
            </div>

            ${warnings.length ? `
                <div class="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
                    <div class="text-[11px] font-mono uppercase tracking-[0.18em] text-amber-300">Needs Attention</div>
                    <div class="mt-3 space-y-2">
                        ${warnings.slice(0, 4).map((warning) => `<div class="text-sm text-amber-100">${escapeHtml(warning)}</div>`).join("")}
                    </div>
                </div>
            ` : ""}
        </div>
    `;
}

function renderDiff() {
    if (!state.diff) {
        if (state.candidateDiff) {
            diffPanel.innerHTML = `
                <div class="panel-shell space-y-4">
                    <div class="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm leading-6 text-rose-100">
                        Candidate changes were generated, but validation failed. This diff is for diagnosis only and is not downloadable as safe output.
                    </div>
                    <div class="space-y-1 font-mono text-xs">${state.candidateDiff.split("\n").map((line) => {
                        let className = "text-zinc-300";
                        if (line.startsWith("+") && !line.startsWith("+++")) {
                            className = "diff-line add";
                        } else if (line.startsWith("-") && !line.startsWith("---")) {
                            className = "diff-line remove";
                        } else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) {
                            className = "diff-line meta";
                        }
                        return `<div class="${className} rounded-md px-2 py-1">${escapeHtml(line || " ")}</div>`;
                    }).join("")}</div>
                </div>
            `;
            updateResultActions();
            return;
        }
        renderPanelPlaceholder(
            diffPanel,
            "Diff preview will appear here",
            "After modernization, this panel will show every added and removed line before anything touches the editor.",
            "Use the diff as the final review checkpoint."
        );
        updateResultActions();
        return;
    }

    diffPanel.innerHTML = `<div class="panel-shell space-y-1">${state.diff.split("\n").map((line) => {
        let className = "text-zinc-300";
        if (line.startsWith("+") && !line.startsWith("+++")) {
            className = "diff-line add";
        } else if (line.startsWith("-") && !line.startsWith("---")) {
            className = "diff-line remove";
        } else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) {
            className = "diff-line meta";
        }
        return `<div class="${className} rounded-md px-2 py-1">${escapeHtml(line || " ")}</div>`;
    }).join("")}</div>`;
    updateResultActions();
}

function renderOutput() {
    if (!state.outputAvailable || !state.newCode) {
        renderTextPlaceholder(
            outputPanel,
            state.validation && !state.validation.success ? "No safe output was produced" : "Output preview will appear here",
            state.validation && !state.validation.success
                ? "Validation failed, so Helix did not expose a downloadable modernized file. Fix the source and run modernization again."
                : "The editor stays untouched until you review the result and choose Apply Changes."
        );
    } else {
        outputPanel.textContent = state.newCode;
    }
    updateOutputDownload();
    updateResultActions();
}

function renderReport() {
    if (!state.report) {
        renderTextPlaceholder(
            reportPanel,
            "Modernization report will appear here",
            "The final report summarizes what was detected, changed, and validated."
        );
    } else {
        reportPanel.textContent = state.report;
    }
}

function renderLogs() {
    const logs = state.logs || [];
    if (!logs.length) {
        terminal.innerHTML = `<div class="text-zinc-500">No execution log yet.</div>`;
        return;
    }

    terminal.innerHTML = logs.map((entry) => {
        const type = inferLogType(entry);
        const color = {
            system: "text-zinc-300",
            analyzer: "text-sky-300",
            success: "text-emerald-300",
            error: "text-rose-300",
            warning: "text-amber-300",
        }[type] || "text-zinc-300";
        return `<div class="animate-fade-in-up rounded-xl border border-white/5 bg-black/20 px-3 py-2 ${color}">${escapeHtml(entry)}</div>`;
    }).join("");
}

function renderMlSummary(status) {
    if (!status) {
        mlBadge.textContent = "Unknown";
        mlBadge.className = "rounded-full border border-white/10 bg-zinc-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-400";
        mlSummary.innerHTML = "Model status unavailable.";
        return;
    }

    if (!status.enabled) {
        mlBadge.textContent = "Disabled";
        mlBadge.className = "rounded-full border border-white/10 bg-zinc-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-400";
        mlSummary.innerHTML = "The ML reasoner is currently disabled.";
        return;
    }

    if (!status.available) {
        mlBadge.textContent = "Pending";
        mlBadge.className = "rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300";
        mlSummary.innerHTML = `Enabled, but the adapter is not ready.${status.error ? `<div class="mt-2 text-rose-300">${escapeHtml(status.error)}</div>` : ""}`;
        return;
    }

    mlBadge.textContent = "Active";
    mlBadge.className = "rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300";
    mlSummary.innerHTML = "Adapter-backed reasoning is available for auxiliary modernization output.";
}

function activateTab(key) {
    Object.entries(tabs).forEach(([tabKey, button]) => {
        button.classList.toggle("active", tabKey === key);
    });

    Object.entries(panels).forEach(([panelKey, panel]) => {
        panel.classList.toggle("hidden", panelKey !== key);
        panel.classList.toggle("panel-shell", panelKey === key);
    });
}

function setStepState(currentKey, completed = []) {
    Object.entries(steps).forEach(([key, element]) => {
        element.classList.remove("current", "done");
        if (completed.includes(key)) {
            element.classList.add("done");
        }
        if (key === currentKey) {
            element.classList.add("current");
        }
    });
}

function setMode(label) {
    modeBadge.textContent = label;
    modeBadge.className = "rounded-full border border-white/10 bg-zinc-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-zinc-300";
}

function setStatus(label) {
    statusBadge.textContent = label;
    statusBadge.className = "rounded-full border border-white/10 bg-zinc-900 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-300";
}

function setFocus(text) {
    focusText.textContent = text;
}

function setAdvancedOpen(open) {
    advancedPanel.classList.toggle("hidden", !open);
    advancedToggleLabel.textContent = open ? "Hide" : "Show";
}

function resetUi(resetHistory = true) {
    updateLineNumbers();
    syncScroll();
    setStepState("analyze");
    setMode("Idle");
    setStatus("Waiting");
    setFocus("Paste legacy Python or load a sample, then analyze the code.");
    summaryStrip.classList.add("hidden");
    renderReview();
    renderDiff();
    renderOutput();
    renderReport();
    terminal.innerHTML = `<div class="text-zinc-500">No execution log yet.</div>`;
    if (resetHistory) {
        runHistory.innerHTML = `<div class="rounded-xl border border-dashed border-white/10 bg-black/20 p-3 text-xs text-zinc-500">Run history will appear here.</div>`;
    }
    activateTab("review");
    setAdvancedOpen(false);
    setPrimaryAction("analyze");
    downloadReport.classList.add("hidden");
    downloadOutput.classList.add("hidden");
    downloadOutputTop.classList.add("hidden");
    updateResultActions();
}

function log(message, type = "system") {
    state.logs.push(message);
    renderLogs();
}

function updateLineNumbers() {
    const lineCount = codeInput.value.split("\n").length;
    lineNumbers.textContent = Array.from({ length: lineCount }, (_, index) => index + 1).join("\n");
}

function syncScroll() {
    lineNumbers.scrollTop = codeInput.scrollTop;
}

function riskToneClasses(risk) {
    if (risk === "HIGH" || risk === "CRITICAL") {
        return "border-rose-500/20 bg-rose-500/10 text-rose-200";
    }
    if (risk === "MEDIUM" || risk === "RESTRICTED") {
        return "border-amber-500/20 bg-amber-500/10 text-amber-200";
    }
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-200";
}

function renderPanelPlaceholder(panel, title, body, hint) {
    panel.innerHTML = `
        <div class="panel-shell rounded-2xl border border-dashed border-white/10 bg-black/20 p-5">
            <div class="text-sm font-medium text-zinc-200">${escapeHtml(title)}</div>
            <div class="mt-2 text-sm leading-6 text-zinc-500">${escapeHtml(body)}</div>
            ${hint ? `<div class="mt-4 text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-600">${escapeHtml(hint)}</div>` : ""}
        </div>
    `;
}

function renderTextPlaceholder(panel, title, body) {
    panel.innerHTML = `${title}\n\n${body}`;
}

async function copyPanelContent(kind) {
    const content = kind === "diff" ? state.diff : state.newCode;
    if (!content) {
        showToast(`No ${kind} available to copy`, "error");
        return;
    }

    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(content);
        } else {
            const probe = document.createElement("textarea");
            probe.value = content;
            probe.setAttribute("readonly", "");
            probe.style.position = "absolute";
            probe.style.left = "-9999px";
            document.body.appendChild(probe);
            probe.select();
            document.execCommand("copy");
            document.body.removeChild(probe);
        }
        showToast(`${kind === "diff" ? "Diff" : "Output"} copied`, "success");
    } catch (error) {
        showToast(`Failed to copy ${kind}`, "error");
    }
}

function updateResultActions() {
    copyDiffBtn.classList.toggle("hidden", !state.diff);
    copyOutputBtn.classList.toggle("hidden", !state.outputAvailable || !state.newCode);
    downloadOutput.classList.toggle("hidden", !state.outputAvailable || !state.newCode);
    downloadOutputTop.classList.toggle("hidden", !state.outputAvailable || !state.newCode);
}

function updateOutputDownload() {
    if (!state.outputAvailable || !state.newCode) {
        downloadOutput.classList.add("hidden");
        downloadOutputTop.classList.add("hidden");
        return;
    }
    const blob = new Blob([state.newCode], { type: "text/x-python" });
    downloadOutput.href = URL.createObjectURL(blob);
    downloadOutput.classList.remove("hidden");
    downloadOutputTop.href = downloadOutput.href;
    downloadOutputTop.classList.remove("hidden");
}

function inferLogType(entry) {
    const text = String(entry).toLowerCase();
    if (text.includes("warning")) return "warning";
    if (text.includes("failed") || text.includes("error") || text.includes("blocked")) return "error";
    if (text.includes("detected") || text.includes("source profile")) return "analyzer";
    if (text.includes("saved run") || text.includes("validated") || text.includes("completed")) return "success";
    return "system";
}

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    const tone = {
        info: "border-white/10 text-zinc-200",
        success: "border-emerald-500/30 text-emerald-100",
        error: "border-rose-500/30 text-rose-100",
    }[type] || "border-white/10 text-zinc-200";
    toast.className = `animate-fade-in-up rounded-2xl border bg-zinc-900/90 px-4 py-3 text-sm shadow-2xl backdrop-blur ${tone}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}

function setPrimaryAction(action) {
    state.primaryAction = action;
    const config = {
        analyze: {
            label: "Analyze Code",
            hint: "Current step: analyze the input",
            disabled: false,
            classes: "rounded-full bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-black transition-colors hover:bg-zinc-200",
        },
        modernize: {
            label: "Modernize Code",
            hint: "Current step: generate the updated result",
            disabled: false,
            classes: "rounded-full bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-black transition-colors hover:bg-zinc-200",
        },
        apply: {
            label: "Apply Changes",
            hint: "Current step: replace the editor with the modernized output",
            disabled: false,
            classes: "rounded-full bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-black transition-colors hover:bg-zinc-200",
        },
        blocked: {
            label: "Blocked",
            hint: "Current step: review issues manually",
            disabled: true,
            classes: "rounded-full border border-rose-500/20 bg-rose-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-rose-200 transition-colors",
        },
        working: {
            label: "Working...",
            hint: "Current step: wait for the pipeline to finish",
            disabled: true,
            classes: "rounded-full border border-white/10 bg-zinc-900 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400 transition-colors",
        },
    }[action];

    runBtn.className = config.classes;
    runBtn.textContent = config.label;
    runBtn.disabled = config.disabled;
    actionHint.textContent = config.hint;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
