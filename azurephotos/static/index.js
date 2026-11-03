/** Keep supported extensions aligned with src.lib.models.media. */
const PHOTO_EXTENSIONS = new Set([
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".webp", ".bmp", ".dib",
    ".tif", ".tiff", ".gif", ".mpo", ".heic", ".heif",
]);
const VIDEO_EXTENSIONS = new Set([
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp", ".3g2", ".ts", ".m2ts",
]);

function getExtension(filename) {
    return typeof filename === "string"
        ? filename.slice(filename.lastIndexOf(".")).trim().toLowerCase()
        : null;
}

function isPhoto(filename) {
    return PHOTO_EXTENSIONS.has(getExtension(filename));
}

function isVideo(filename) {
    return VIDEO_EXTENSIONS.has(getExtension(filename));
}

/** Keep album-name validation aligned with src.api.albums.is_valid_album_name. */
function isValidAlbumName(name, existingNames) {
    if (typeof name !== "string") {
        return false;
    }
    name = name.trim();
    if (!name || name.length > 1024 || existingNames.includes(name)) {
        return false;
    }
    for (const char of name) {
        const code = char.codePointAt(0);
        if (code <= 0x1F || (code >= 0x7F && code <= 0x9F) || "/\\#?".includes(char)) {
            return false;
        }
    }
    return true;
}

async function request(path, method = "POST", body) {
    const response = await fetch(path, { method, body });
    if (!response.ok) {
        throw new Error(`${response.status}: ${response.statusText}`);
    }
    return response;
}

/** Workers claim an item before awaiting, so each item runs exactly once. */
async function runWithProgress(items, action, concurrency) {
    items = Array.from(items);
    const totalCount = items.length;
    const errors = [];
    let next = 0;
    let completed = 0;

    function updateProgress() {
        for (const [status, count] of [
            ["success", completed - errors.length],
            ["failure", errors.length],
        ]) {
            const percent = totalCount ? Math.round(count / totalCount * 100) : 0;
            $(`#${status}Progress`).css("width", `${percent}%`)
                .attr("aria-valuenow", percent).text(`${count} / ${totalCount}`);
        }
    }

    async function worker() {
        while (next < totalCount) {
            const item = items[next++];
            try {
                await action(item);
            } catch (error) {
                errors.push({ item, error });
            }
            completed++;
            updateProgress();
        }
    }

    updateProgress();
    await Promise.all(Array.from({ length: Math.min(concurrency, totalCount) }, worker));
    return { successCount: completed - errors.length, failureCount: errors.length, totalCount, errors };
}

// Flask provides `albums` on both pages and `album` on an album page.
$(document).ready(() => {
    const inAlbum = typeof album !== "undefined";
    const mediaGrid = document.getElementById("mediaGrid");
    const modalElement = document.getElementById("fullsizeModal");
    const viewerStage = document.getElementById("fullsizeModalBody");
    const viewer = bootstrap.Modal.getOrCreateInstance(modalElement);
    const uploads = new Map();
    const scrollPositions = {};
    let currentView = null;
    let viewedItem = null;
    let viewerOpener = null;
    let busy = false;
    let gesture = null;
    let suppressPhotoClick = false;

    function mediaButtons() {
        return Array.from(mediaGrid.querySelectorAll(".photo-open"));
    }

    function selectedFiles() {
        return Array.from(mediaGrid.querySelectorAll(".photo-checkbox:checked"), box => box.value);
    }

    function updateUI() {
        const count = selectedFiles().length;
        document.body.classList.toggle("is-selecting", count > 0);
        document.getElementById("selectionBar").hidden = count === 0;
        document.getElementById("mediaEmptyState").hidden = mediaGrid.children.length > 0;
        $("#selectionCount").text(`${count} selected`);
        $("#clearSelectionBtn, #formFileLg, .photo-checkbox, .photo-open").prop("disabled", busy);
        $("#submitUpload").prop("disabled", busy || uploads.size === 0);
        $("#deleteSelectedBtn, #moveSelectedBtn").prop("disabled", busy || count === 0);
        $("#viewerDeleteBtn").prop("disabled", busy || !viewedItem);
        $("#viewerMoveBtn").prop("disabled",
            busy || !viewedItem || $("#viewerMoveMenu .dropdown-item").length === 0);
        $(".app-navigation a").attr("aria-disabled", String(busy));
    }

    function clearSelection() {
        $(".photo-checkbox").prop("checked", false);
        updateUI();
    }

    async function runOperation(items, action, verb, concurrency = 4) {
        if (busy || items.length === 0) {
            return false;
        }
        busy = true;
        updateUI();
        $("#operationProgress").show().find(".progress-bar").addClass("progress-bar-animated");
        try {
            const result = await runWithProgress(items, action, concurrency);
            if (result.failureCount) {
                console.warn(`Some ${verb} failed:`, result.errors);
                alert(`${result.successCount}/${result.totalCount} ${verb} succeeded`);
            }
            return result.failureCount === 0;
        } finally {
            busy = false;
            updateUI();
            $("#operationProgress .progress-bar").removeClass("progress-bar-animated");
            setTimeout(() => {
                if (!busy) {
                    $("#operationProgress").hide();
                }
            }, 500);
        }
    }

    // Navigation retains each screen's scroll position.
    function showView() {
        const name = location.hash.slice(1);
        const nextView = document.getElementById(name)?.classList.contains("app-panel") ? name : "photos";
        if (nextView !== currentView) {
            if (currentView !== null) {
                scrollPositions[currentView] = window.scrollY;
                clearSelection();
            }
            document.querySelectorAll(".app-panel").forEach(panel => {
                panel.hidden = panel.id !== nextView;
            });
            currentView = nextView;
            window.scrollTo(0, scrollPositions[nextView] || 0);
        }
        const active = inAlbum && nextView === "photos" ? "albums" : nextView;
        $(".app-navigation a").each(function () {
            $(this).attr("aria-current", this.dataset.view === active ? "page" : null);
        });
    }

    window.addEventListener("hashchange", showView);
    $(".app-navigation a").on("click", event => {
        if (busy) {
            event.preventDefault();
        }
    });
    $("#clearSelectionBtn").on("click", clearSelection);
    $(".photo-checkbox").on("change", updateUI);
    $(mediaGrid).on("click", ".photo-open", function (event) {
        if (busy) {
            return;
        }
        if (suppressPhotoClick && event.detail > 0) {
            suppressPhotoClick = false;
            return;
        }
        if (selectedFiles().length) {
            const box = $(this).siblings(".photo-checkbox");
            box.prop("checked", !box.prop("checked"));
            updateUI();
        } else {
            viewer.show(this);
        }
    });
    $(mediaGrid).on("contextmenu", ".photo-open", event => event.preventDefault());

    // A touch on a thumbnail can become a long press; a touch in the viewer can become a swipe.
    function cancelGesture() {
        clearTimeout(gesture?.timer);
        gesture = null;
    }

    document.addEventListener("pointerdown", event => {
        cancelGesture();
        if (!event.isPrimary) {
            return;
        }
        suppressPhotoClick = false;
        if (event.pointerType === "mouse" || busy) {
            return;
        }
        const button = event.target.closest(".photo-open");
        const inViewer = viewerStage.contains(event.target) && modalElement.classList.contains("show");
        if ((!button && !inViewer) || (button && selectedFiles().length)) {
            return;
        }
        const video = event.target.closest("video");
        if (video && event.clientY >= video.getBoundingClientRect().bottom - 72) {
            return; // Leave native video controls available.
        }
        gesture = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, button };
        if (button) {
            gesture.timer = setTimeout(() => {
                $(button).siblings(".photo-checkbox").prop("checked", true);
                suppressPhotoClick = true;
                updateUI();
            }, 450);
        }
    });
    document.addEventListener("pointermove", event => {
        if (gesture?.pointerId !== event.pointerId) {
            return;
        }
        const dx = event.clientX - gesture.x;
        const dy = event.clientY - gesture.y;
        if (gesture.button) {
            if (Math.hypot(dx, dy) > 10) {
                cancelGesture();
            }
        } else if (Math.abs(dy) > 20 && Math.abs(dy) > Math.abs(dx)) {
            cancelGesture();
        } else if (Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            viewerStage.setPointerCapture(event.pointerId);
        }
    });
    document.addEventListener("pointerup", event => {
        const completed = gesture;
        cancelGesture();
        if (!completed || completed.button || completed.pointerId !== event.pointerId) {
            return;
        }
        const dx = event.clientX - completed.x;
        const dy = event.clientY - completed.y;
        if (Math.abs(dx) >= 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            navigateViewer(dx < 0 ? 1 : -1, true);
        }
    });
    document.addEventListener("pointercancel", cancelGesture);

    // The viewer holds one original image or video, never a separate preview tier.
    function clearViewerMedia() {
        const video = viewerStage.querySelector("video");
        if (video) {
            if (document.pictureInPictureElement === video) {
                document.exitPictureInPicture().catch(error => {
                    console.warn("Could not exit Picture-in-picture:", error);
                });
            }
            video.pause();
            video.removeAttribute("src");
            video.load();
        }
        viewerStage.replaceChildren();
        viewerStage.setAttribute("aria-busy", "false");
    }

    function setViewerInfo(open) {
        document.getElementById("viewerInfoPanel").hidden = !open;
        $("#viewerInfoBtn").attr("aria-expanded", String(open));
    }

    function showViewerNotice(message) {
        $("#viewerNotice").text(message).prop("hidden", false);
    }

    function showMedia(button, direction = 0) {
        clearViewerMedia();
        viewedItem = button;
        const { filename, full, mediaType, date } = button.dataset;
        const video = mediaType === "video";
        $("#fullsizeModalLabel, #viewerInfoFilename").text(filename);
        $("#viewerOriginal, #viewerDownload").attr("href", full);
        $("#viewerNotice").prop("hidden", true);
        $("#viewerInfoType").text(`${video ? "Video" : "Photo"} (${getExtension(filename).slice(1).toUpperCase()})`);
        $("#viewerInfoDimensions, #viewerInfoDuration").text("Loading...");
        $("#viewerInfoDurationLabel, #viewerInfoDuration").prop("hidden", !video);
        const timestamp = date ? new Date(date) : null;
        const validDate = timestamp && !Number.isNaN(timestamp.getTime());
        $("#viewerInfoDate").text(validDate ? timestamp.toLocaleString() : "Not available")
            .attr("datetime", validDate ? date : null);
        if (timestamp && !validDate) {
            console.warn("Invalid date metadata for", filename);
        }
        updateUI();
        viewerStage.setAttribute("aria-busy", "true");

        const status = $("<p>", { class: "viewer-status", role: "status", text: "Loading..." })[0];
        const element = document.createElement(video ? "video" : "img");
        element.className = "viewer-media w-100 h-100 object-fit-contain";
        element.draggable = false;
        if (video) {
            element.controls = true;
            element.playsInline = true;
            element.preload = "metadata";
            element.title = filename;
        } else {
            element.alt = filename;
        }
        if (direction) {
            element.style.opacity = "0";
            element.style.setProperty("--slide-from", `${direction * 40}px`);
        }
        element.addEventListener(video ? "loadedmetadata" : "load", () => {
            if (!viewerStage.contains(element)) {
                return;
            }
            status.hidden = true;
            viewerStage.setAttribute("aria-busy", "false");
            element.style.removeProperty("opacity");
            if (direction) {
                element.classList.add("viewer-enter");
            }
            const width = video ? element.videoWidth : element.naturalWidth;
            const height = video ? element.videoHeight : element.naturalHeight;
            $("#viewerInfoDimensions").text(width > 0 && height > 0 ? `${width} x ${height}` : "Not available");
            if (video) {
                const seconds = Math.floor(element.duration);
                $("#viewerInfoDuration").text(Number.isFinite(seconds)
                    ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`
                    : "Not available");
            }
        });
        element.addEventListener("error", () => {
            if (viewerStage.contains(element)) {
                element.style.removeProperty("opacity");
                status.hidden = false;
                status.textContent = "Could not display this file. Open the original to view or save it.";
                viewerStage.setAttribute("aria-busy", "false");
                $("#viewerInfoDimensions, #viewerInfoDuration").text("Not available");
            }
        });
        viewerStage.replaceChildren(element, status);
        element.src = full;
        if (history.state?.azurePhotosMedia) {
            history.replaceState({ ...history.state, azurePhotosMedia: filename }, "");
        }
    }

    function navigateViewer(direction, animate = false) {
        if (busy || !modalElement.classList.contains("show")) {
            return;
        }
        const buttons = mediaButtons();
        const next = buttons[buttons.indexOf(viewedItem) + direction];
        if (next) {
            showMedia(next, animate ? direction : 0);
        }
    }

    // One history entry lets Back close the viewer and Forward reopen it.
    function syncViewerHistory() {
        const button = mediaButtons().find(item => item.dataset.filename === history.state?.azurePhotosMedia);
        if (!button) {
            viewer.hide();
        } else if (!modalElement.classList.contains("show")) {
            viewer.show(button);
        } else if (button !== viewedItem) {
            showMedia(button);
        }
    }

    $("#fullsizeModal").on("show.bs.modal", event => {
        viewerOpener = event.relatedTarget;
        showMedia(viewerOpener);
        if (!history.state?.azurePhotosMedia) {
            history.pushState({ ...history.state, azurePhotosMedia: viewedItem.dataset.filename }, "");
        }
    }).on("shown.bs.modal", () => {
        if (!history.state?.azurePhotosMedia) {
            viewer.hide();
        }
    }).on("hide.bs.modal", () => {
        cancelGesture();
        if (history.state?.azurePhotosMedia) {
            history.back();
        }
    }).on("hidden.bs.modal", () => {
        clearViewerMedia();
        viewedItem = null;
        setViewerInfo(false);
        $("#viewerNotice").prop("hidden", true);
        viewerOpener?.focus({ preventScroll: true });
        updateUI();
        syncViewerHistory();
    });
    window.addEventListener("popstate", () => {
        showView();
        syncViewerHistory();
    });
    $("#viewerInfoBtn").on("click", () => setViewerInfo(document.getElementById("viewerInfoPanel").hidden));
    $("#viewerInfoClose").on("click", () => {
        setViewerInfo(false);
        $("#viewerInfoBtn").trigger("focus");
    });
    $("#viewerShareBtn").on("click", () => showViewerNotice("Anonymous sharing is not implemented in this prototype."));
    $("#viewerDownload").on("click", () => showViewerNotice(
        "The original opens in a new tab. Use your browser's save/download option."));
    $(document).on("keydown", event => {
        if (modalElement.classList.contains("show")) {
            if (!event.target.closest("video") && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
                event.preventDefault();
                navigateViewer(event.key === "ArrowLeft" ? -1 : 1);
            }
        } else if (event.key === "Escape" && !busy) {
            clearSelection();
        }
    });

    // Uploads are keyed by the same filename/size/date fingerprint used for deduplication.
    function enqueueFiles(files) {
        for (const file of files) {
            const id = `${file.name}:${file.size}:${file.lastModified}`;
            if (uploads.has(id)) {
                continue;
            }
            const previewUrl = URL.createObjectURL(file);
            uploads.set(id, { file, previewUrl });
            const card = $("<div>", { class: "photo-card position-relative" });
            const thumbnailClass = "img-thumbnail d-block w-100 p-0 border-0 object-fit-cover";
            if (file.type.startsWith("image/")) {
                card.append($("<img>", { class: thumbnailClass, src: previewUrl, title: file.name, draggable: false }));
            } else if (file.type.startsWith("video/")) {
                card.append($("<video>", { class: thumbnailClass, src: previewUrl, title: file.name })
                    .prop({ muted: true, playsInline: true, preload: "metadata" }));
            }
            card.append($("<button>", {
                type: "button",
                class: "btn btn-sm btn-danger icon-button position-absolute bottom-0 start-0 m-2 remove-file-btn",
                "aria-label": `Remove ${file.name} from upload queue`,
                text: "x",
            }));
            $("#uploadSelectedFiles").append($("<div>", { class: "col", "data-upload-id": id }).append(card));
        }
        updateUI();
    }

    $("#uploadDropZone").on("dragover", event => {
        event.preventDefault();
        $("#uploadDropZone").addClass("border-primary bg-primary-subtle");
    }).on("dragleave drop", event => {
        event.preventDefault();
        $("#uploadDropZone").removeClass("border-primary bg-primary-subtle");
    }).on("drop", event => {
        if (!busy) {
            enqueueFiles(event.originalEvent.dataTransfer.files);
        }
    });
    $("#formFileLg").on("change", function () {
        enqueueFiles(this.files);
    });
    $("#uploadSelectedFiles").on("click", ".remove-file-btn", function () {
        const preview = this.closest("[data-upload-id]");
        const item = uploads.get(preview.dataset.uploadId);
        if (item) {
            URL.revokeObjectURL(item.previewUrl);
            uploads.delete(preview.dataset.uploadId);
            preview.remove();
            updateUI();
        }
    });
    $("#uploadForm").on("submit", async event => {
        event.preventDefault();
        const files = Array.from(uploads.values(), item => item.file).filter(file => {
            if (!isPhoto(file.name) && !isVideo(file.name)) {
                alert(`${file.name} is not a supported extension`);
                return false;
            }
            if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) {
                alert(`${file.name} is not a photo nor a video`);
                return false;
            }
            return true;
        });
        const path = inAlbum ? `/upload/${encodeURIComponent(album)}` : "/upload";
        const success = await runOperation(files, file => {
            const data = new FormData();
            data.append("upload", file);
            data.append("dateTaken", new Date(file.lastModified).toISOString());
            return request(path, "POST", data);
        }, "uploads", 2);
        if (success) {
            location.hash = "photos";
            location.reload();
        }
    });
    window.addEventListener("pagehide", () => {
        for (const item of uploads.values()) {
            URL.revokeObjectURL(item.previewUrl);
        }
    });

    // Bulk actions and viewer actions use the same requests and progress handling.
    function removeMediaItem(filename) {
        const buttons = mediaButtons();
        const button = buttons.find(item => item.dataset.filename === filename);
        const index = buttons.indexOf(button);
        button?.closest(".col").remove();
        if (viewedItem === button) {
            const remaining = mediaButtons();
            if (remaining.length) {
                showMedia(remaining[Math.min(index, remaining.length - 1)]);
            } else {
                viewer.hide();
            }
        }
        updateUI();
    }

    async function deleteMediaItems(files) {
        if (busy || files.length === 0) {
            return;
        }
        const message = inAlbum
            ? `Remove ${files.length} items from this album? The originals will be kept.`
            : `Delete ${files.length} original files? This cannot be undone.`;
        if (!confirm(message)) {
            return;
        }
        const path = inAlbum ? `/api/albums/${encodeURIComponent(album)}` : "/delete";
        if (await runOperation(files, file => request(`${path}/${encodeURIComponent(file)}`, "DELETE")
            .then(() => removeMediaItem(file)), "deletes")) {
            clearSelection();
        }
    }

    async function moveMediaItems(files, targetAlbum) {
        if (busy || files.length === 0 || !confirm(`Move ${files.length} items to '${targetAlbum}'?`)) {
            return;
        }
        const query = inAlbum ? new URLSearchParams({ currentAlbum: album }).toString() : "";
        const path = `/api/albums/${encodeURIComponent(targetAlbum)}`;
        if (await runOperation(files, file => request(`${path}/${encodeURIComponent(file)}?${query}`)
            .then(() => removeMediaItem(file)), "moves")) {
            clearSelection();
        }
    }

    $("#deleteSelectedBtn").on("click", () => deleteMediaItems(selectedFiles()));
    $("#viewerDeleteBtn").on("click", () => {
        if (viewedItem) {
            deleteMediaItems([viewedItem.dataset.filename]);
        }
    });
    $("#moveAlbumMenu .dropdown-item, #viewerMoveMenu .dropdown-item").on("click", function () {
        const files = this.closest("#viewerMoveMenu")
            ? (viewedItem ? [viewedItem.dataset.filename] : [])
            : selectedFiles();
        moveMediaItems(files, this.dataset.targetAlbum);
    });

    // Album forms retain the existing API and validation rules.
    $("#createAlbumCard").on("click", () => {
        $("#createAlbumFormContainer").removeClass("d-none");
        $("#createAlbumInput").trigger("focus");
    });
    $("#createAlbumCancel").on("click", () => {
        $("#createAlbumFormContainer form")[0].reset();
        $("#createAlbumInput").removeClass("is-valid is-invalid");
        $("#createAlbumSubmit").prop("disabled", true);
        $("#createAlbumFormContainer").addClass("d-none");
    });
    $("#createAlbumInput").on("input", function () {
        const valid = isValidAlbumName(this.value, albums);
        $(this).toggleClass("is-valid", valid).toggleClass("is-invalid", !valid);
        $("#createAlbumSubmit").prop("disabled", !valid);
    });
    $("#createAlbumFormContainer form").on("submit", async event => {
        event.preventDefault();
        const name = $("#createAlbumInput").val().trim();
        try {
            await request(`/api/albums/${encodeURIComponent(name)}`);
            location.reload();
        } catch (error) {
            $("#createAlbumInput").addClass("is-invalid");
            console.warn("Could not create album:", error);
            alert(error.message);
        }
    });
    $("#deleteAlbumBtn").on("click", async () => {
        if (!confirm("Are you sure you want to delete this album?")) {
            return;
        }
        try {
            await request(`/api/albums/${encodeURIComponent(album)}`, "DELETE");
            location.href = "/#albums";
        } catch (error) {
            console.warn("Could not delete album:", error);
            alert(error.message);
        }
    });
    $("#renameAlbumBtn").on("click", async () => {
        $("#renameAlbumBtn, #deleteAlbumBtn").prop("disabled", true);
        try {
            const input = prompt("Enter new album name");
            if (input === null) {
                return;
            }
            const name = input.trim();
            if (!name) {
                alert("Album name cannot be only whitespace");
                return;
            }
            await request(`/api/albums/${encodeURIComponent(album)}/rename/${encodeURIComponent(name)}`, "PUT");
            location.href = `/albums/${encodeURIComponent(name)}`;
        } catch (error) {
            console.warn("Could not rename album:", error);
            alert(error.message);
        } finally {
            $("#renameAlbumBtn, #deleteAlbumBtn").prop("disabled", false);
        }
    });

    showView();
    syncViewerHistory();
    updateUI();
});
