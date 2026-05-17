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
    if (typeof filename !== 'string') {
        return null;
    }

    const lastIdx = filename.lastIndexOf(".");
    const extension = filename.slice(lastIdx).trim().toLowerCase();
    return extension;
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
    if (!trimmedAlbumName.trim() || trimmedAlbumName.length > 1024) {
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

    if (existingAlbumNames.includes(trimmedAlbumName)) {
        return false;
    }

    return true;
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
 */
function doWithProgressBarWithConcurrency(items, action, concurrency) {
    items = Array.from(items);
    const totalCount = items.length;

    let index = 0;
    let active = 0;
    let successCount = 0;
    let failureCount = 0;
    const errors = [];

    function updateProgressBar() {
        const successPercent = Math.round((successCount / totalCount) * 100);
        const failurePercent = Math.round((failureCount / totalCount) * 100);

        $("#successProgress")
            .css("width", successPercent + "%")
            .attr("aria-valuenow", successPercent)
            .text(`${successCount} / ${totalCount}`)
        $("#failureProgress")
            .css("width", failurePercent + "%")
            .attr("aria-valuenow", failurePercent)
            .text(`${failureCount} / ${totalCount}`)
    }

    return new Promise((resolve) => {
        function next() {
            if (index === totalCount && active === 0) {
                resolve({
                    successCount,
                    failureCount,
                    totalCount,
                    errors
                });
                return;
            }

            while (active < concurrency && index < totalCount) {
                const item = items[index++];
                active++;

                action(item)
                    .then(() => {
                        successCount++;
                    })
                    .catch((error) => {
                        failureCount++;
                        errors.push({
                            item,
                            error
                        });
                    })
                    .finally(() =>{
                        active--;
                        updateProgressBar();
                        next();
                    })
            }
        }

        updateProgressBar();
        next();
    })
}

/**
 * Upload a single file by HTTP POSTing to a particular path.
 * 
 * @param {File} file File to upload
 * @param {string} path API path to send request
 * @returns {Promise<void>}
 */
function uploadFile(file, path) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append("upload", file);

        console.log(file);
        const lastModified = new Date(file.lastModified);
        formData.append("dateTaken", lastModified.toISOString());

        const xhr = new XMLHttpRequest();
        xhr.open("POST", path);

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve();
            } else {
                reject(xhr.status);
            }
        };
        xhr.onerror = () => {
            reject("network error");
        }

        xhr.send(formData);
    });
}

/**
 * Delete a single file by HTTP DELETEing to a particular path.
 * 
 * @param {string} file File name with extension
 * @param {string} path API path to send request
 * @returns {Promise<void>}
 */
function deleteFile(file, path) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("DELETE", path);

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                const thumbnailQuery = `[src="/thumbnail/${file}"]`;
                const deletedThumbnail = document.querySelector(thumbnailQuery);
                if (deletedThumbnail) {
                    deletedThumbnail.closest(".col").remove();
                }

                resolve();
            } else {
                reject(xhr.status);
            }
        };
        xhr.onerror = () => {
            reject("network error");
        };

        xhr.send();
    });
}

/**
 * Move a single file to an album by HTTP POSTing to a particular path.
 * 
 * @param {string} file File name with extension
 * @param {string} path API path to send request
 * @returns {Promise<void>}
 */
function moveToAlbum(file, path) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", path);

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                const thumbnailQuery = `[src="/thumbnail/${file}"]`;
                const movedThumbnail = document.querySelector(thumbnailQuery);
                if (movedThumbnail) {
                    movedThumbnail.closest(".col").remove();
                }

                resolve();
            } else {
                reject(xhr.status);
            }
        };
        xhr.onerror = () => {
            reject("network error");
        }

        xhr.send();
    });
}

/**
 * Get fingerprint representing file for dedupe.
 * @param {File} file 
 * @returns {string}
 */
function fileFingerprint(file) {
    return [
        file.name,
        file.size,
        file.lastModified
    ].join(":");
}

// Some variables are passed here from HTML from Flask.
// We'll have `albums` on all pages and `album` on an album page
$(document).ready(() => {
    /**
     * Last viewed photo or video in modal
     * @type {string?}
     */
    let modalPhotoName = null;
    /**
     * Items selected by checkbox
     * @type {Set<string>}
     */
    let checkedItems = new Set();
    /**
     * Items queued for upload
     * @type {Array<{
     *  id: `${string}-${string}-${string}-${string}-${string}`;
     *  fingerprint: string;
     *  file: File;
     *  previewUrl: string;
     * }>}
     */
    let itemsToUpload = [];
    /**
     * Collection of fingerprints of files queued for upload
     * @type {Set<string>}
     */
    let itemsToUploadFingerprints = new Set();

    // Open fullsize modal when clicking on a thumbnail
    $("#fullsizeModal").on('show.bs.modal', function (event) {
        const trigger = event.relatedTarget;
        const fullSrc = trigger.getAttribute('data-full');
        modalPhotoName = fullSrc.slice("/fullsize/".length);

        const fullsizeModalBody = document.getElementById("fullsizeModalBody");

        // Clear any existing parts of the modal body
        fullsizeModalBody.innerHTML = "";

        // Build a new img or video inside the modal body
        if (isVideo(fullSrc)) {
            const video = document.createElement("video");
            video.className = "img-fluid";
            video.controls = true;
            video.title = modalPhotoName;
            video.draggable = false;

            const source = document.createElement("source");
            source.src = fullSrc;
            source.type = "video/mp4";

            video.appendChild(source);
            fullsizeModalBody.appendChild(video);
            video.load();
        } else {
            const img = document.createElement("img");
            img.className = "img-fluid";
            img.src = fullSrc;
            img.alt = modalPhotoName;
            innerHeight.draggable = false;

            fullsizeModalBody.appendChild(img);
        }
    });

    // Close fullsize modal
    $("#fullsizeModal").on("hidden.bs.modal", async function () {
        // Clear any existing parts of the modal body
        // This should also stop a video that was playing
        const fullsizeModalBody = document.getElementById("fullsizeModalBody");
        const video = fullsizeModalBody.querySelector("video");

        if (video) {
            // Try to exit picture-in-picture if active
            try {
                if (document.pictureInPictureElement) {
                    await document.exitPictureInPicture();
                }
            } catch (err) {
                console.warn("Could not exit Picture-in-picture:", err);
            }

            // Pause video playback
            video.pause();

            // Remove video source to stop buffering/audio
            video.removeAttribute("src");
            const source = video.querySelector("source");
            if (source) {
                source.removeAttribute("src");
            }

            // Force reload of (non) video
            video.load();
        }

        // Clear modal body
        fullsizeModalBody.innerHTML = "";
        modalPhotoName = null;
    });

    // Drag and drop photos for upload
    $("#uploadDropZone").on("dragover", function (event) {
        event.preventDefault();

        $("#uploadDropZone").addClass("border-primary bg-primary-subtle");
    });
    $("#uploadDropZone").on("dragleave drop", function (event) {
        event.preventDefault();

        $("#uploadDropZone").removeClass("border-primary bg-primary-subtle");
    });
    $("#uploadDropZone").on("drop", function (event) {
        const files = event.originalEvent.dataTransfer.files;
        enqueueFilesToUpload(files);
    });
    $("#formFileLg").on("change", function() {
        enqueueFilesToUpload(this.files);
    });
    /**
     * Add files to upload queue and render them in the UI.
     * @param {File[]} files 
     */
    function enqueueFilesToUpload(files) {
        for (const file of files) {
            const fingerprint = fileFingerprint(file);
            if (itemsToUploadFingerprints.has(fingerprint)) {
                continue;
            }
            itemsToUploadFingerprints.add(fingerprint);

            const item = {
                id: crypto.randomUUID(),
                fingerprint,
                file,
                previewUrl: URL.createObjectURL(file)
            };

            itemsToUpload.push(item);
            appendUploadPreview(item);
        }
    }
    /**
     * Add an item to the UI for rendering
     * @param {{
     *  id: `${string}-${string}-${string}-${string}-${string}`;
     *  fingerprint: string;
     *  file: File;
     *  previewUrl: string;
     * }} item 
     */
    function appendUploadPreview(item) {
        const isImage = item.file.type.startsWith("image/");
        const isVideo = item.file.type.startsWith("video/");

        const col = $("<div>")
            .addClass("col")
            .attr("data-upload-id", item.id);
        const photoCard = $("<div>")
            .addClass("photo-card position-relative");

        let previewElement = null;
        if (isImage) {
            previewElement = $("<img>")
                .addClass("img-fluid img-thumbnail")
                .attr("src", item.previewUrl)
                .attr("title", item.file.name)
                .prop("draggable", false);
        } else if (isVideo) {
            previewElement = $("<video>")
                .addClass("img-thumbnail")
                .attr("title", item.file.name)
                .prop("muted", true)
                .prop("draggable", false)
                .prop("playsInline", true)
                .prop("preload", "metadata");
            
            const source = $("<source>")
                .attr("src", item.previewUrl)
                .attr("type", item.file.type);

            previewElement.append(source);
        }

        const removeButton = $("<button>")
            .addClass(
                "btn btn-sm btn-danger photo-action remove-file-btn"
            )
            .attr("type", "button")
            .text("x");

        if (previewElement) {
            photoCard.append(previewElement);
        }
        photoCard.append(removeButton);
        col.append(photoCard);

        $("#uploadSelectedFiles").append(col);
    }

    // Remove enqueued file from upload
    $("#uploadSelectedFiles").on("click", ".remove-file-btn", function () {
        const previewElement = $(this)
            .closest("[data-upload-id]");
        const uploadId = previewElement.data("upload-id");

        const index = itemsToUpload.findIndex(x => x.id === uploadId);
        if (index === -1) {
            return;
        }

        const item = itemsToUpload[index];
        itemsToUploadFingerprints.delete(item.fingerprint);
        itemsToUpload.splice(index, 1);
        URL.revokeObjectURL(item.previewUrl);
        
        previewElement.remove();
    });

    // Submit photos and videos for upload
    $("#uploadForm").on('submit', function (event) {
        event.preventDefault();

        const isAlbum = (typeof album) !== "undefined";
        const path = isAlbum ? `/upload/${album}` : `/upload`;

        const validFiles = Array.from(itemsToUpload)
            .map(item => item.file)
            .filter(file => {
                if (!isPhoto(file.name) && !isVideo(file.name)) {
                    alert(`${file.name} is not a supported extension`);
                    return false;
                }

                if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) {
                    alert(`${file.name} is not a photo nor a video`);
                    return false
                }

                return true;
            });

        if (validFiles.length === 0) {
            return;
            // TODO: Should we show some error here?
        }

        $("#formFileLg").prop("disabled", true);
        $("#submitUpload").prop("disabled", true);
        $("#operationProgress .progress-bar").addClass("progress-bar-animated");
        $("#operationProgress").show();

        doWithProgressBarWithConcurrency(
            validFiles,
            (file) => uploadFile(file, path),
            2
        )
            .then(({ successCount, failureCount, totalCount, errors }) => {
                if (failureCount > 0) {
                    console.warn("Some uploads failed:", errors);
                    alert(`${successCount}/${totalCount} uploads succeeded`);
                    return;
                }

                location.reload();
            })
            .finally(() => {
                $("#formFileLg").prop("disabled", false);
                $("#submitUpload").prop("disabled", false);
                $("#operationProgress .progress-bar").removeClass("progress-bar-animated");
                setTimeout(() => { 
                    $("#operationProgress").hide();
                }, 500);
            });
    });

    // Delete photos and videos
    $(".photo-action.delete-btn").click(function (event) {
        const isAlbum = (typeof album) !== "undefined";
        const basePath = isAlbum ? `/api/albums/${album}` : `/delete`;

        // If we clicked the delete button on an unchecked item, add it to selected items
        const selected = event.currentTarget.dataset.selected;
        $(`.photo-checkbox[value='${selected}']`)
            .prop("checked", true)
            .trigger("change")

        const confirmMessage = `Are you sure you want to remove ${checkedItems.size} items${isAlbum ? ' from this album' : ''}?`;
        if (!confirm(confirmMessage)) {
            return;
        }

        $("#operationProgress .progress-bar").addClass("progress-bar-animated");
        $("#operationProgress").show();

        doWithProgressBarWithConcurrency(
            checkedItems,
            (file) => deleteFile(file, `${basePath}/${file}`),
            4
        )
            .then(({ successCount, failureCount, totalCount, errors }) => {
                if (failureCount) {
                    console.warn("Some deletes failed:", errors);
                    alert(`${successCount}/${totalCount} deletes succeeded`);
                    return;
                }

                checkedItems.clear();
            })
            .finally(() => {
                $("#operationProgress .progress-bar").removeClass("progress-bar-animated");
                setTimeout(() => { 
                    $("#operationProgress").hide(); 
                }, 500);
            });
    });

    // Place photos and videos in album
    $(".photo-action.album-btn").siblings("ul").find("li .dropdown-item").each(function () {
        const li = $(this);
        const targetAlbum = li.text()
        const inAlbum = (typeof album) !== "undefined"

        li.click((_) => {
            const name = li.closest("ul.dropdown-menu")
                .siblings(".photo-action.album-btn")
                .data("name")

            // Add photo to selection
            $(`.photo-checkbox[value='${name}']`)
                .prop("checked", true)
                .trigger("change")

            if (!confirm(`Are you sure you want to move ${checkedItems.size} items to '${targetAlbum}?'`)) {
                return;
            }

            $("#operationProgress .progress-bar").addClass("progress-bar-animated");
            $("#operationProgress").show();

            const basePath = `/api/albums/${targetAlbum}`;
            const queryString = inAlbum 
                ? new URLSearchParams({
                    "currentAlbum": album
                }).toString()
                : "";
            doWithProgressBarWithConcurrency(
                checkedItems,
                (file) => moveToAlbum(file, `${basePath}/${file}?${queryString}`),
                4
            )
                .then(({ successCount, failureCount, totalCount, errors }) => {
                    if (failureCount) {
                        console.warn("Some moves failed:", errors);
                        alert(`${successCount}/${totalCount} moves succeeded`);
                        return;
                    }
                    
                    if (modalPhotoName !== null) {
                        bootstrap.Modal.getInstance(fullsizeModal).hide();
                        modalPhotoName = null;
                    }

                    checkedItems.clear();
                })
                .finally(() => {
                    $("#operationProgress .progress-bar").removeClass("progress-bar-animated");
                    setTimeout(() => { 
                        $("#operationProgress").hide(); 
                    }, 500);
                });
        });
    });

    // Select photos and videos
    $(".photo-checkbox").on("change", function (_) {
        const selected = $(this).val()
        if (this.checked) {
            checkedItems.add(selected)
        } else {
            checkedItems.delete(selected)
        }
    });

    // Clear selected photos and videos
    $(document).on("keydown", function (event) {
        if (event.key === "Escape") {
            // Do not uncheck anything if the modal was closing
            if (event.target.id === "fullsizeModal") {
                return;
            }

            $(".photo-checkbox")
                .prop("checked", false)
                .trigger("change")
            checkedItems.clear();
        }
    });

    // Show create album form
    $("#createAlbumCard").click(function() {
        $("#createAlbumFormContainer").removeClass("d-none");
        $("#createAlbumInput").trigger("focus");
    });

    // Hide create album form
    $("#createAlbumCancel").click(function (e) {
        // Prevent the click even from going up to #createAlbumCard, which would reopen the form
        e.stopPropagation();

        $("#createAlbumFormContainer form")[0].reset();
        $("#createAlbumInput").removeClass("is-valid is-invalid");
        $("#createAlbumSubmit").prop("disabled", true);
        $("#createAlbumFormContainer").addClass("d-none");
    });

    // Validate create album input
    $("#createAlbumInput").on("input", function() {
        const input = $(this);
        const valid = isValidAlbumName(input.val(), albums); // TODO: Could albums be a set?
        if (valid) {
            input.removeClass("is-invalid").addClass("is-valid");
        } else {
            input.removeClass("is-valid").addClass("is-invalid");
        }

        $("#createAlbumSubmit").prop("disabled", !valid);
    });

    // Submit create album form
    // Precondition: Validation is successful
    $("#createAlbumFormContainer form").submit(function (e) {
        e.preventDefault();
        
        const input = $("#createAlbumInput");
        const albumName = input.val().trim();
        fetch(`/api/albums/${encodeURIComponent(albumName)}`, { method: "POST" })
            .then(response => {
                if (response.ok) {
                    // TODO: Instead of reloading, can we just append to the albums list with a thumbnail of /static/album_thumbnail
                    albums.push(albumName);
                    window.location.reload();
                    console.log(response);
                } else {
                    input.addClass("is-invalid");
                    console.log(response);
                }
            })
            .catch(console.error);
    });

    // Delete album
    $("#deleteAlbumBtn").click(function (_) {
        if (!confirm("Are you sure you want to delete this album?")) {
            return;
        }

        fetch(`/api/albums/${album}`, { method: "DELETE" })
            .then(response => {
                if (response.ok) {
                    window.location.href = "/";
                } else {
                    console.log(response);
                }
            }).catch(error => {
                console.log(error);
            });
    });

    // Rename album
    $("#renameAlbumBtn").click(function (_) {
        const renameBtn = $(this);
        const deleteBtn = $("#deleteAlbumBtn");
        renameBtn.prop("disabled", true);
        deleteBtn.prop("disabled", true);

        const newAlbumInput = prompt("Enter new album name");

        if (newAlbumInput === null) { // User cancelled rename
            renameBtn.prop("disabled", false);
            deleteBtn.prop("disabled", false);
            return;
        }

        const newAlbumName = newAlbumInput.trim();
        if (newAlbumName === "") {
            alert("Album name cannot be only whitespace");
            renameBtn.prop("disabled", false);
            deleteBtn.prop("disabled", false);
            return;
        }

        fetch(`/api/albums/${album}/rename/${newAlbumName}`, { method: "PUT" })
            .then(response => {
                if (response.ok) {
                    album = newAlbumName;
                    window.location.href = `/albums/${newAlbumName}`;
                } else {
                    console.log(response);
                }
            })
            .catch(error => {
                console.log(error);
                alert("Rename failed");
            })
            .finally(() => {
                renameBtn.prop("disabled", false);
                deleteBtn.prop("disabled", false);
            });
    });
});
