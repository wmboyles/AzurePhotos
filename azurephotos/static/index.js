// imageUrls is passed here from HTML from Flask
// We'll also have `albums` on the main page and `album` on an album page
$(document).ready(() => {
    // Last viewed photo in modal
    let modalPhotoName = null;
    // Photos selected by checkbox
    let selectedPhotos = new Set();

    // Open modal when clicking on a thumbnail
    $("#imageModal").on('show.bs.modal', function (event) {
        const trigger = event.relatedTarget;
        const fullSrc = trigger.getAttribute('data-full');

        document.getElementById('modalImage').src = fullSrc;
        modalPhotoName = fullSrc.slice("/fullsize/".length);
    });

    // Submit photos for upload
    $("#uploadForm").on('submit', function (event) {
        event.preventDefault();

        const isAlbum = typeof (album) !== "undefined";
        const path = isAlbum ? `/upload/${album}` : `/upload`

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

    // Delete photo
    $(".photo-action.delete-btn").click(function (event) {
        const photo = event.currentTarget.dataset.photo

        // Add photo to selection
        $(`.photo-checkbox[value='${photo}']`)
            .prop("checked", true)
            .trigger("change")

        const isAlbum = (typeof album) !== "undefined";
        if (!confirm(isAlbum ?
            `Are you sure you want to remove ${selectedPhotos.size} photos from this album?` :
            `Are you sure you want to delete ${selectedPhotos.size} photos?`)) {
            return;
        }

        selectedPhotos.forEach(selectedPhoto => {
            const deleteUrl = isAlbum ? `/api/albums/${album}/${selectedPhoto}` : `/delete/${selectedPhoto}`

            fetch(deleteUrl, { method: "DELETE" })
                .then(response => {
                    if (response.ok) {
                        const deletedThumbnail = document.querySelector(`[data-full="/fullsize/${selectedPhoto}"]`)
                        if (deletedThumbnail) {
                            deletedThumbnail.closest(".col").remove();
                        }
                        selectedPhotos.delete(selectedPhoto)
                    } else {
                        console.log(response);
                    }
                })
                .catch(error => {
                    console.log(error);
                });
        })
    });

    // Place photo in album
    $(".photo-action.album-btn").siblings("ul").find("li .dropdown-item").each(function () {
        const li = $(this);
        const album = li.text()

        li.click((_) => {
            const photo = li.closest("ul.dropdown-menu")
                .siblings(".photo-action.album-btn")
                .data("photo")

            // Add photo to selection
            $(`.photo-checkbox[value='${photo}']`)
                .prop("checked", true)
                .trigger("change")

            if (!confirm(`Are you sure you want to move ${selectedPhotos.size} photos to ${album}?`)) {
                return;
            }

            selectedPhotos.forEach(selectedPhoto => {
                fetch(`/api/albums/${album}/${selectedPhoto}`, { method: "POST" })
                    .then(response => {
                        if (response.ok) {
                            const movedThumbnail = document.querySelector(`[data-full="/fullsize/${selectedPhoto}"]`)
                            if (movedThumbnail) {
                                movedThumbnail.closest(".col").remove();
                            }
                            if (modalPhotoName !== null) {
                                bootstrap.Modal.getInstance(imageModal).hide();
                                modalPhotoName = null;
                            }
                            selectedPhotos.delete(selectedPhoto)
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

    // Select photo(s)
    $(".photo-checkbox").on("change", function (_) {
        const photo = $(this).val()
        if (this.checked) {
            selectedPhotos.add(photo)
        } else {
            selectedPhotos.delete(photo)
        }
    });

    // Clear selected photos
    $(document).on("keydown", function (event) {
        if (event.key === "Escape") {
            // Do not uncheck anything if the modal was closing
            if (event.target.id === "imageModal") {
                return;
            }

            $(".photo-checkbox")
                .prop("checked", false)
                .trigger("change")
            selectedPhotos.clear();
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
        alert("Are you sure you want to delete this album?");
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