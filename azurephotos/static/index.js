// imageUrls is passed here from HTML from Flask
// We'll also have `albums` on the main page and `album` on an album page
$(document).ready(() => {
    // Last viewed photo in modal
    let modalPhotoName = null;
    // Photos selected by checkbox
    let selectedPhotos = new Set();

    // Open modal when clicking on a thumbnail
    function showModal(event) {
        const trigger = event.relatedTarget;
        const fullSrc = trigger.getAttribute('data-full');

        document.getElementById('modalImage').src = fullSrc;
        modalPhotoName = fullSrc.slice("/fullsize/".length);
    }

    function deleteImage(photoName) {
        const isAlbum = (typeof album) !== "undefined";
        if (!confirm(isAlbum ?
            `Are you sure you want to remove ${photoName} from this album?` :
            `Are you sure you want to delete ${photoName}?`)) {
            return;
        }

        const deleteUrl = isAlbum ? `/api/albums/${album}/${photoName}` : `/delete/${photoName}`

        fetch(deleteUrl, { method: "DELETE" })
            .then(response => {
                if (response.ok) {
                    const deletedThumbnail = document.querySelector(`[data-full="/fullsize/${photoName}"]`)
                    if (deletedThumbnail) {
                        deletedThumbnail.closest(".col").remove();
                    }
                } else {
                    console.log(response);
                }
            })
            .catch(error => {
                console.log(error);
            });
    }

    function uploadPhotos(event) {
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
    }

    $("#imageModal").on('show.bs.modal', showModal);

    $("#uploadForm").on('submit', uploadPhotos);

    $("#deleteBtn").click(function() {
        deleteImage(modalPhotoName);
        bootstrap.Modal.getInstance(imageModal).hide();
        modalPhotoName = null;
    });

    $(".photo-action.delete-btn").click(function() {
        const photo = $(this).data("photo");
        deleteImage(photo);
    });

    $(".photo-checkbox").on("change", function() {
        const photo = $(this).val()
        if (this.checked) {
            selectedPhotos.add(photo)
        } else {
            selectedPhotos.delete(photo)
        }
    });

    /* ALBUMS */
    function createAlbum() {
        const albumName = prompt("Enter album name");
        fetch(`/api/albums/${albumName}`, { method: "POST" })
            .then(response => {
                albums.push(albumName);
                window.location.reload();
            }).catch(error => {
                console.log(error);
            });
    }

    function deleteAlbum() {
        alert("Are you sure you want to delete this album?");
        fetch(`/api/albums/${album}`, { method: "DELETE" })
            .then(_ => {
                window.location.href = "/";
            }).catch(error => {
                console.log(error);
            });
    }

    function renameAlbum() {
        const newAlbumName = prompt("Enter new album name");
        fetch(`/api/albums/${album}/rename/${newAlbumName}`, { method: "PUT" })
            .then(response => {
                album = newAlbumName;
                window.location.href = `/albums/${newAlbumName}`;
            }).catch(error => {
                console.log(error);
            });
    }

    function addToAlbum(album) {
        fetch(`/api/albums/${album}/${modalPhotoName}`, { method: "POST" })
            .then(response => {
                if (response.ok) {
                    const movedThumbnail = document.querySelector(`[data-full="/fullsize/${modalPhotoName}"]`)
                    if (movedThumbnail) {
                        movedThumbnail.closest(".col").remove();
                    }
                    bootstrap.Modal.getInstance(imageModal).hide();
                    modalPhotoName = null;
                } else {
                    console.log(response);
                }
            })
            .catch(error => {
                console.log(error)
            });
    }

    $("#createAlbumBtn").click(createAlbum);

    $("#deleteAlbumBtn").click(deleteAlbum);

    $("#renameAlbumBtn").click(renameAlbum);

    $("#addToAlbumBtn").siblings("ul").find("li .dropdown-item").each(function () {
        const button = $(this);
        const albumName = button.text();
        button.click(() => addToAlbum(albumName))
        // button.attr("onclick", addToAlbum(albumName))
    });
});