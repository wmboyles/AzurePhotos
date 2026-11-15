function createViewer({ mediaGrid, getExtension, isBusy, onDelete, onMove }) {
    const modalElement = document.getElementById("fullsizeModal");
    const viewerStage = document.getElementById("fullsizeModalBody");
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    let viewedItem = null;
    let opener = null;
    let swipe = null;

    function mediaButtons() {
        return Array.from(mediaGrid.querySelectorAll(".photo-open"));
    }

    function isOpen() {
        return modalElement.classList.contains("show");
    }

    function updateControls() {
        $("#viewerDeleteBtn").prop("disabled", isBusy() || !viewedItem);
        $("#viewerMoveBtn").prop("disabled",
            isBusy() || !viewedItem || $("#viewerMoveMenu .dropdown-item").length === 0);
    }

    // The viewer holds one original image or video, never a separate preview tier.
    function clearMedia() {
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

    function setInfo(open) {
        document.getElementById("viewerInfoPanel").hidden = !open;
        $("#viewerInfoBtn").attr("aria-expanded", String(open));
    }

    function showNotice(message) {
        $("#viewerNotice").text(message).prop("hidden", false);
    }

    function showMedia(button, direction = 0) {
        clearMedia();
        viewedItem = button;
        const { filename, full, mediaType, date } = button.dataset;
        const video = mediaType === "video";
        $("#fullsizeModalLabel, #viewerInfoFilename").text(filename);
        $("#viewerDownload").attr("href", full);
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
        updateControls();
        viewerStage.setAttribute("aria-busy", "true");

        const status = $("<p>", { class: "viewer-status", role: "status", text: "Loading..." })[0];
        const element = document.createElement(video ? "video" : "img");
        element.className = "img-fluid w-100 h-100";
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
                status.textContent = "Could not display this file. Use Download to open the original.";
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

    function navigate(direction, animate = false) {
        if (isBusy() || !isOpen()) {
            return;
        }
        const buttons = mediaButtons();
        const next = buttons[buttons.indexOf(viewedItem) + direction];
        if (next) {
            showMedia(next, animate ? direction : 0);
        }
    }

    // One history entry lets Back close the viewer and Forward reopen it.
    function syncHistory() {
        const button = mediaButtons().find(item => item.dataset.filename === history.state?.azurePhotosMedia);
        if (!button) {
            modal.hide();
        } else if (!isOpen()) {
            modal.show(button);
        } else if (button !== viewedItem) {
            showMedia(button);
        }
    }

    $("#fullsizeModal").on("show.bs.modal", event => {
        opener = event.relatedTarget;
        showMedia(opener);
        if (!history.state?.azurePhotosMedia) {
            history.pushState({ ...history.state, azurePhotosMedia: viewedItem.dataset.filename }, "");
        }
    }).on("shown.bs.modal", () => {
        if (!history.state?.azurePhotosMedia) {
            modal.hide();
        }
    }).on("hide.bs.modal", () => {
        swipe = null;
        if (history.state?.azurePhotosMedia) {
            history.back();
        }
    }).on("hidden.bs.modal", () => {
        clearMedia();
        viewedItem = null;
        setInfo(false);
        $("#viewerNotice").prop("hidden", true);
        opener?.focus({ preventScroll: true });
        updateControls();
        syncHistory();
    });
    $("#viewerInfoBtn").on("click", () => setInfo(document.getElementById("viewerInfoPanel").hidden));
    $("#viewerInfoClose").on("click", () => {
        setInfo(false);
        $("#viewerInfoBtn").trigger("focus");
    });
    $("#viewerShareBtn").on("click", () => showNotice("Anonymous sharing is not implemented in this prototype."));
    $("#viewerDownload").on("click", () => showNotice(
        "The original opens in a new tab. Use your browser's save/download option."));
    $("#viewerDeleteBtn").on("click", () => {
        if (viewedItem) {
            onDelete([viewedItem.dataset.filename]);
        }
    });
    $("#viewerMoveMenu .dropdown-item").on("click", function () {
        if (viewedItem) {
            onMove([viewedItem.dataset.filename], this.dataset.targetAlbum);
        }
    });
    $(document).on("keydown", event => {
        if (isOpen() && !event.target.closest("video") &&
            (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
            event.preventDefault();
            navigate(event.key === "ArrowLeft" ? -1 : 1);
        }
    });

    document.addEventListener("pointerdown", event => {
        swipe = null;
        if (!event.isPrimary || event.pointerType === "mouse" || isBusy() ||
            !isOpen() || !viewerStage.contains(event.target)) {
            return;
        }
        const video = event.target.closest("video");
        if (video && event.clientY >= video.getBoundingClientRect().bottom - 72) {
            return; // Leave native video controls available.
        }
        swipe = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    });
    document.addEventListener("pointermove", event => {
        if (swipe?.pointerId !== event.pointerId) {
            return;
        }
        const dx = event.clientX - swipe.x;
        const dy = event.clientY - swipe.y;
        if (Math.abs(dy) > 20 && Math.abs(dy) > Math.abs(dx)) {
            swipe = null;
        } else if (Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            viewerStage.setPointerCapture(event.pointerId);
        }
    });
    document.addEventListener("pointerup", event => {
        const completed = swipe;
        swipe = null;
        if (!completed || completed.pointerId !== event.pointerId) {
            return;
        }
        const dx = event.clientX - completed.x;
        const dy = event.clientY - completed.y;
        if (Math.abs(dx) >= 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            navigate(dx < 0 ? 1 : -1, true);
        }
    });
    document.addEventListener("pointercancel", () => { swipe = null; });

    function mediaRemoved(button) {
        if (viewedItem === button) {
            modal.hide();
        }
    }

    return {
        open: button => modal.show(button),
        isOpen,
        updateControls,
        syncHistory,
        mediaRemoved,
    };
}
