/**
 * Collection of file extensions representing supported photo types.
 * Should match src.lib.models.media.PHOTO_EXTENSIONS
 */
const PHOTO_EXTENSIONS = new Set([
    ".jpg", ".jpeg", ".jpe", ".jfif",
    ".png",
    ".webp",
    ".bmp", ".dib",
    ".tif", ".tiff",
    ".gif",
    ".mpo",
    ".heic", ".heif",
]);

/**
 * Collection of file extensions representing supported video types.
 * Should match src.lib.models.media.VIDEO_EXTENSIONS
 */
const VIDEO_EXTENSIONS = new Set([
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".3gp",
    ".3g2",
    ".ts",
    ".m2ts",
]);

/**
 * Get the extension from a file name.
 * @example getExtension("video.mp4") === ".mp4"
 * @param {string} filename File name with extension
 * @returns {string?}
 */
function getExtension(filename) {
    if (typeof filename !== "string") {
        return null;
    }

    const lastIdx = filename.lastIndexOf(".");
    return filename.slice(lastIdx).trim().toLowerCase();
}

/**
 * Determine if a filename is a supported photo type.
 * @param {string} filename File name with extension
 * @returns {boolean}
 */
function isPhoto(filename) {
    const extension = getExtension(filename);
    return PHOTO_EXTENSIONS.has(extension);
}

/**
 * Determine if a filename is a supported video type.
 * @param {string} filename File name with extension
 * @returns {boolean}
 */
function isVideo(filename) {
    const extension = getExtension(filename);
    return VIDEO_EXTENSIONS.has(extension);
}

/**
 * Validates if an album name is valid or not.
 * This logic should match src.api.albums.is_valid_album_name
 * @param {string | null | undefined} albumName 
 * @param {Array<string>} existingAlbumNames
 * @returns {boolean}
 */
function isValidAlbumName(albumName, existingAlbumNames) {
    if (typeof albumName !== "string") {
        return false;
    }

    const trimmedAlbumName = albumName.trim();
    if (!trimmedAlbumName || trimmedAlbumName.length > 1024 || existingAlbumNames.includes(trimmedAlbumName)) {
        return false;
    }

    for (const char of trimmedAlbumName) {
        const o = char.codePointAt(0);

        // Unicode control characters
        // U+0000 to U+001F and U+007F to U+009F
        if (o <= 0x1F || (o >= 0x7F && o <= 0x9F)) {
            return false;
        }

        // / \ # ?
        if (o === 47 || o === 92 || o === 35 || o === 63) {
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

/**
 * Perform an action on a collection of items
 * Update the progress bar as actions are successful or failed
 * Limit the number of concurrent actions run at once.
 * 
 * @param {Iterable<T> | ArrayLike<T>} items Collection of items to act upon
 * @param {(item: T) => Promise<void>} action Action to perform on each item
 * @param {number} concurrency Max concurrency limit
 * @returns {Promise<{
 *  successCount: number;
 *  failureCount: number;
 *  totalCount: number;
 *  errors: Array<{
 *      item: T;
 *      error: unknown
 *  }>;
 * }>}
 * 
 * Workers claim an item before awaiting, so each item runs exactly once.
 */
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
            $(`#${status}Progress`)
                .css("width", `${percent}%`)
                .attr("aria-valuenow", percent)
                .text(`${count} / ${totalCount}`);
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
    await Promise.all(Array.from({
        length: Math.min(concurrency, totalCount) 
    }, worker));
    
    return { 
        successCount: completed - errors.length,
        failureCount: errors.length,
        totalCount: totalCount, 
        errors: errors
    };
}

function updateView(pageViews, active) {
    pageViews.each(function () {
        $(this).toggleClass("d-none", this.id !== active);
    });
}

function updateNavigation(navLinks, active) {
    navLinks.each(function () {
        const selected = this.dataset.view === active;
        $(this).toggleClass("text-primary", selected).toggleClass("text-secondary", !selected)
            .attr("aria-current", selected ? "page" : null);
    });
}

// Flask provides `albums` on both pages and `album` on an album page.
$(document).ready(() => {
    const inAlbum = typeof album !== "undefined";
    const mediaGrid = document.getElementById("mediaGrid");
    const views = $("section[data-page-view]");
    const navLinks = $('nav[aria-label="Main navigation"] a[data-view]');
    const uploads = new Map();
    const scrollPositions = {};
    let currentView = null;
    let busy = false;
    let longPress = null;
    let suppressPhotoClick = false;
    const viewer = createViewer({
        mediaGrid,
        getExtension,
        isBusy: () => busy,
        onDelete: deleteMediaItems,
        onMove: moveMediaItems,
    });

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
        viewer.updateControls();
        navLinks.attr("aria-disabled", String(busy)).toggleClass("opacity-50", busy);
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
    function updatePage() {
        const name = location.hash.slice(1);
        const nextView = views.toArray().some(view => view.id === name) ? name : "photos";
        if (nextView !== currentView) {
            if (currentView !== null) {
                scrollPositions[currentView] = window.scrollY;
                clearSelection();
            }
            updateView(views, nextView);
            currentView = nextView;
            window.scrollTo(0, scrollPositions[nextView] || 0);
        }
        updateNavigation(navLinks, inAlbum && nextView === "photos" ? "albums" : nextView);
    }

    $(window).on("hashchange", updatePage);
    navLinks.on("click", event => {
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
            viewer.open(this);
        }
    });
    $(mediaGrid).on("contextmenu", ".photo-open", event => event.preventDefault());

    function cancelLongPress() {
        clearTimeout(longPress?.timer);
        longPress = null;
    }

    document.addEventListener("pointerdown", event => {
        cancelLongPress();
        if (!event.isPrimary) {
            return;
        }
        suppressPhotoClick = false;
        if (event.pointerType === "mouse" || busy) {
            return;
        }
        const button = event.target.closest(".photo-open");
        if (!button || selectedFiles().length) {
            return;
        }
        longPress = {
            pointerId: event.pointerId,
            x: event.clientX,
            y: event.clientY,
            timer: setTimeout(() => {
                $(button).siblings(".photo-checkbox").prop("checked", true);
                suppressPhotoClick = true;
                updateUI();
            }, 450),
        };
    });
    document.addEventListener("pointermove", event => {
        if (longPress?.pointerId !== event.pointerId) {
            return;
        }
        if (Math.hypot(event.clientX - longPress.x, event.clientY - longPress.y) > 10) {
            cancelLongPress();
        }
    });
    document.addEventListener("pointerup", cancelLongPress);
    document.addEventListener("pointercancel", cancelLongPress);
    window.addEventListener("popstate", () => {
        updatePage();
        viewer.syncHistory();
    });
    $(document).on("keydown", event => {
        if (!viewer.isOpen() && event.key === "Escape" && !busy) {
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
    // Bulk actions and viewer actions use the same requests and progress handling.
    function removeMediaItem(filename) {
        const buttons = mediaButtons();
        const button = buttons.find(item => item.dataset.filename === filename);
        button?.closest(".col").remove();
        viewer.mediaRemoved(button);
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
    $("#moveAlbumMenu .dropdown-item").on("click", function () {
        moveMediaItems(selectedFiles(), this.dataset.targetAlbum);
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

    updatePage();
    viewer.syncHistory();
    updateUI();
});
