// Some variables are passed here from HTML from Flask.
// We'll have `albums` on the main page, `album` on an album page, and `videoUrls` on the video page.
$(document).ready(() => {
    // Last viewed photo in modal
    let modalPhotoName = null;
    // Photos or videos selected by checkbox
    let selectedItems = new Set();

    // Open modal when clicking on a thumbnail
    $("#imageModal").on('show.bs.modal', function (event) {
        const trigger = event.relatedTarget;
        const fullSrc = trigger.getAttribute('data-full');

        document.getElementById('modalImage').src = fullSrc;
        modalPhotoName = fullSrc.slice("/fullsize/".length);
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
            const isVideo = String(selectedItem).endsWith(".mp4") // TODO: Handle other video types
            fetch(deleteUrl, { method: "DELETE" })
                .then(response => {
                    if (response.ok) {
                        const selectedItemQuery = isVideo ? `[src="/api/videos/${selectedItem}"]` : `[src="/thumbnail/${selectedItem}"]`
                        const deletedThumbnail = document.querySelector(selectedItemQuery)
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

    // Place photo in album
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
                            const isVideo = String(selectedItem).endsWith(".mp4"); // TODO: Handle other video types
                            const selectedItemsQuery = isVideo ? `[src="/api/videos/${selectedItem}"]` : `[data-full="/fullsize/${selectedItem}"]`;
                            const movedThumbnail = document.querySelector(selectedItemsQuery);
                            if (movedThumbnail) {
                                movedThumbnail.closest(".col").remove();
                            }
                            if (modalPhotoName !== null) {
                                bootstrap.Modal.getInstance(imageModal).hide();
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

    // Select photo(s) or video(s)
    $(".photo-checkbox").on("change", function (_) {
        const selected = $(this).val()
        if (this.checked) {
            selectedItems.add(selected)
        } else {
            selectedItems.delete(selected)
        }
    });

    // Clear selected photo(s) or video(s)
    $(document).on("keydown", function (event) {
        if (event.key === "Escape") {
            // Do not uncheck anything if the modal was closing
            if (event.target.id === "imageModal") {
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