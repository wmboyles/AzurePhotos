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

        if (video)
        {
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

        const isAlbum = typeof (album) !== "undefined";
        const path = isAlbum  ? `/upload/${album}` : `/upload`;

        const input = document.getElementById("formFileLg");
        const files = input.files;
        const formData = new FormData();

        for (let i = 0; i < files.length; i++) {
            const file = files[i];

            const filename = file.name;
            if (!isPhoto(filename) && !isVideo(filename)) {
                alert(`${filename} is not a supported extension`);
                return;
            }

            const fileType = file.type;
            if (!fileType.startsWith("image/") && !fileType.startsWith("video/")) {
                alert(`${filename} is not a photo nor a video`);
                return;
            }

            formData.append("upload", file);

            // Get last modified
            const dateTaken = new Date(file.lastModified);
            formData.append("dateTaken", dateTaken.toISOString());
        }

        $("#submitUpload").prop("disabled", true); // disable before upload
        fetch(path, { method: "POST", body: formData })
            .then(response => {
                if (!response.ok) {
                    alert("Upload failed");
                    console.log(response);
                } else {
                    location.reload();
                }
            })
            .catch(error => {
                console.log(error);
            })
            .finally(() => {
                $("#submitUpload").prop("disabled", false) // re-enable submit
            });
        // Submit button should be re-enabled on page refresh.
    });

    // Delete photo or video
    $(".photo-action.delete-btn").click(function (event) {
        const isAlbum = (typeof album) !== "undefined";
        
        // If we clicked the delete button on an unchecked item, add it to selected items
        const selected = event.currentTarget.dataset.selected;
        $(`.photo-checkbox[value='${selected}']`)
            .prop("checked", true)
            .trigger("change")

        const confirmMessage = `Are you sure you want to remove ${selectedItems.size} items${isAlbum ? ' from this album' : ''}?`;
        if (!confirm(confirmMessage)) {
            return;
        }

        selectedItems.forEach(selectedItem => {
            const deleteUrl = isAlbum ? `/api/albums/${album}/${selectedItem}` : `/delete/${selectedItem}`;
            fetch(deleteUrl, { method: "DELETE" })
                .then(response => {
                    if (response.ok) {
                        const selectedItemQuery = `[src="/thumbnail/${selectedItem}"]`;
                        const deletedThumbnail = document.querySelector(selectedItemQuery);
                        if (deletedThumbnail) {
                            deletedThumbnail.closest(".col").remove();
                        }
                        selectedItems.delete(selectedItem)
                    } else {
                        console.log(response);
                    }
                })
                .catch(error => {
                    console.log(error);
                });
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
        const newAlbumName = prompt("Enter new album name");
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
            });
    });
});
