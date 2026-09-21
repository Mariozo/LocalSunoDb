        const modal = document.getElementById("style-modal");
        const modalTitle = document.getElementById("modal-title");
        const modalText = document.getElementById("modal-text");
        const modalClose = document.getElementById("modal-close");


        modalClose.addEventListener("click", () => {
            modal.style.display = "none";
        });

        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.style.display = "none";
            }
        });
