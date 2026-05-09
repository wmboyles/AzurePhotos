// Should match src.lib.models.media.PHOTO_EXTENSIONS
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

// Should match src.lib.models.media.VIDEO_EXTENSIONS
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

function getExtension(filename) {
    if (typeof filename !== 'string') {
        return null;
    }

    const lastIdx = filename.lastIndexOf(".");
    const extension = filename.slice(lastIdx).trim().toLowerCase();
    return extension;
}

function isPhoto(filename) {
    const extension = getExtension(filename);
    return PHOTO_EXTENSIONS.has(extension);
}

function isVideo(filename) {
    const extension = getExtension(filename);
    return VIDEO_EXTENSIONS.has(extension);
}

function uploadWithConcurrency(files, path, concurrency) {
    let index = 0;
    let active = 0;

    const totalFiles = files.length;
    let successCount = 0;
    let failureCount = 0;
    const errors = [];

    function updateProgressBar() {
        const successPercent = Math.round((successCount / totalFiles) * 100);
        const failurePercent = Math.round((failureCount / totalFiles) * 100);

        $("#successProgress")
            .css("width", successPercent + "%")
            .attr("aria-valuenow", successPercent)
            .text(`${successCount} / ${totalFiles}`)
        $("#failureProgress")
            .css("width", failurePercent + "%")
            .attr("aria-valuenow", failurePercent)
            .text(`${failureCount} / ${totalFiles}`)
    }

    function uploadSingle(file) {
        return new Promise((resolve) => {
            const formData = new FormData();
            formData.append("upload", file);

            const dateTaken = new Date(file.lastModified);
            formData.append("dateTaken", dateTaken.toISOString());

            const xhr = new XMLHttpRequest();
            xhr.open("POST", path);

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    successCount++;
                } else {
                    failureCount++;
                    errors.push({
                        file: file.name,
                        status: xhr.status
                    });
                }

                updateProgressBar();
                resolve();
            };
            xhr.onerror = () => {
                failureCount++;
                errors.push({
                    file: file.name,
                    status: "network error"
                });

                updateProgressBar();
                resolve();
            };

            xhr.send(formData);
        });
    }

    return new Promise((resolve) => {
        function next() {
            if (index === files.length && active === 0) {
                resolve({ successCount, totalFiles, errors });
                return;
            }

            while (active < concurrency && index < files.length) {
                const file = files[index++];
                active++;

                uploadSingle(file).then(() => {
                    active--;
                    next();
                });
            }
        }

        successCount = 0;
        updateProgressBar();

        next();
    });
}

function deleteWithConcurrency(filenames, path, concurrency) {
    filenames = Array.from(filenames);
    let index = 0;
    let active = 0;

    const totalFiles = filenames.length;
    let successCount = 0;
    let failureCount = 0;
    const errors = [];

    function updateProgressBar() {
        const successPercent = Math.round((successCount / totalFiles) * 100);
        const failurePercent = Math.round((failureCount / totalFiles) * 100);

        $("#successProgress")
            .css("width", successPercent + "%")
            .attr("aria-valuenow", successPercent)
            .text(`${successCount} / ${totalFiles}`)
        $("#failureProgress")
            .css("width", failurePercent + "%")
            .attr("aria-valuenow", failurePercent)
            .text(`${failureCount} / ${totalFiles}`)
    }

    function deleteSingle(filename) {
        return new Promise((resolve) => {
            const xhr = new XMLHttpRequest();
            const pathWithFile = `${path}/${filename}`
            xhr.open("DELETE", pathWithFile);

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    successCount++;

                    const thumbnailQuery = `[src="/thumbnail/${filename}"]`;
                    const deletedThumbnail = document.querySelector(thumbnailQuery);
                    if (deletedThumbnail) {
                        deletedThumbnail.closest(".col").remove();
                    }
                } else {
                    failureCount++;
                    errors.push({
                        file: filename,
                        status: xhr.status
                    });
                }

                updateProgressBar();
                resolve();
            };
            xhr.onerror = () => {
                failureCount++;
                errors.push({
                    file: filename,
                    status: "network error"
                });

                updateProgressBar();
                resolve();
            };

            xhr.send();
        })
    }

    return new Promise((resolve) => {
        function next() {
            if (index === filenames.length && active === 0) {
                resolve({ successCount, totalFiles, errors });
                return;
            }

            while(active < concurrency && index < filenames.length) {
                const filename = filenames[index++];
                active++;

                deleteSingle(filename).then(() => {
                    active--;
                    next();
                });
            }
        }

        successCount = 0;
        updateProgressBar();

        next();
    });
}

// Some variables are passed here from HTML from Flask.
// We'll have `albums` on the main page, `album` on an album page, and `videoUrls` on the video page.
$(document).ready(() => {
    // Last viewed photo or video in modal
    let modalPhotoName = null;
    // Photo or video selected by checkbox
    let selectedItems = new Set();

    // Open modal when clicking on a thumbnail
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

            fullsizeModalBody.appendChild(img);
        }
    });

    // Close modal
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

    // Submit photos and videos for upload
    $("#uploadForm").on('submit', function (event) {
        event.preventDefault();

        const isAlbum = (typeof album) !== "undefined";
        const path = isAlbum ? `/upload/${album}` : `/upload`;

        const input = document.getElementById("formFileLg");
        const validFiles = Array.from(input.files).filter(file => {
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
            // TODO: Should we show some erorr here?
        }

        $("#formFileLg").prop("disabled", true);
        $("#submitUpload").prop("disabled", true);
        $("#operationProgress .progress-bar").addClass("progress-bar-animated");
        $("#operationProgress").show();

        uploadWithConcurrency(validFiles, path, 2)
            .then(({ successCount, totalFiles, errors }) => {
                if (errors.length > 0) {
                    console.warn("Some uploads failed:", errors);
                    alert(`${successCount}/${totalFiles} uploads succeeded`);
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

        const confirmMessage = `Are you sure you want to remove ${selectedItems.size} items${isAlbum ? ' from this album' : ''}?`;
        if (!confirm(confirmMessage)) {
            return;
        }

        $("#operationProgress .progress-bar").addClass("progress-bar-animated");
        $("#operationProgress").show();

        deleteWithConcurrency(selectedItems, basePath, 4)
            .then(({ successCount, totalFiles, errors }) => {
                if (errors.length > 0) {
                    console.warn("Some deletes failed:", errors);
                    alert(`${successCount}/${totalFiles} deletes succeeded`);
                    return;
                }

                selectedItems.clear();
            })
            .finally(() => {
                $("#operationProgress .progress-bar").removeClass("progress-bar-animated");
                setTimeout(() => { 
                    $("#operationProgress").hide(); 
                }, 500);
            });
    });

    // Place photo or video in album
    $(".photo-action.album-btn").siblings("ul").find("li .dropdown-item").each(function () {
        const li = $(this);
        const album = li.text()

        li.click((_) => {
            const name = li.closest("ul.dropdown-menu")
                .siblings(".photo-action.album-btn")
                .data("name")

            // Add photo to selection
            $(`.photo-checkbox[value='${name}']`)
                .prop("checked", true)
                .trigger("change")

            if (!confirm(`Are you sure you want to move ${selectedItems.size} items to '${album}?'`)) {
                return;
            }

            selectedItems.forEach(selectedItem => {
                fetch(`/api/albums/${album}/${selectedItem}`, { method: "POST" })
                    .then(response => {
                        if (response.ok) {
                            const selectedItemsQuery = `[data-full="/fullsize/${selectedItem}"]`;
                            const movedThumbnail = document.querySelector(selectedItemsQuery);
                            if (movedThumbnail) {
                                movedThumbnail.closest(".col").remove();
                            }
                            if (modalPhotoName !== null) {
                                bootstrap.Modal.getInstance(fullsizeModal).hide();
                                modalPhotoName = null;
                            }
                            selectedItems.delete(selectedItem)
                        } else {
                            console.log(response);
                        }
                    })
                    .catch(error => {
                        console.log(error)
                    });
            });
        });
    });

    // Select photos and videos
    $(".photo-checkbox").on("change", function (_) {
        const selected = $(this).val()
        if (this.checked) {
            selectedItems.add(selected)
        } else {
            selectedItems.delete(selected)
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
            selectedItems.clear();
        }
    });

    // Create album
    $("#createAlbumBtn").click(function (_) {
        const albumName = prompt("Enter album name");
        fetch(`/api/albums/${albumName}`, { method: "POST" })
            .then(response => {
                if (response.ok) {
                    // TODO: Instead of reloading, can we just append to the albums list with a thumbnail of /static/album_thumbnail
                    albums.push(albumName);
                    window.location.reload();
                } else {
                    console.log(response);
                }
            })
            .catch(error => {
                console.log(error);
            });
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
