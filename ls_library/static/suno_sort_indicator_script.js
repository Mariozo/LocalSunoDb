        function setSortIndicators(column, direction) {
            headers.forEach((h) => {
                h.classList.remove("sort-asc");
                h.classList.remove("sort-desc");
            });

            const activeHeader = Array.from(headers).find((h) => parseInt(h.dataset.column, 10) === column);
            if (activeHeader) {
                activeHeader.classList.add(direction === "asc" ? "sort-asc" : "sort-desc");
            }
        }