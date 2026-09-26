        function setupPlayerBlock(playerBlock, audioSrc, waveformSource, trackId, endCallback) {
            const audio = getPlayerBlockAudio(playerBlock);
            const backButton = playerBlock.querySelector(".back-btn");

            audio.addEventListener("play", () => {
                const fragment = playerBlock.closest(".fragment-row");
                if (fragment) {
                    fragment.querySelectorAll("audio").forEach((otherAudio) => {
                        if (otherAudio !== audio && !otherAudio.paused) {
                            otherAudio.pause();
                        }
                    });
                }
                if (lastActiveAudio && lastActiveAudio !== audio && !lastActiveAudio.paused) {
                    lastActiveAudio.pause();
                }
                lastActiveAudio = audio;
                const fragmentRow = playerBlock.closest(".fragment-row");
                const trackRow = fragmentRow
                    ? fragmentRow.previousElementSibling
                    : null;
                if (
                    trackRow &&
                    trackRow.classList.contains("track-row")
                ) {
                    setPlayerHighlight(trackRow, fragmentRow);
                    const playButton = trackRow.querySelector(".play-btn");
                    if (playButton && playerBlock.classList.contains("suno-block")) {
                        playButton.innerText = "❚❚";
                        playButton.classList.add("active");
                    }
                }
            });

            audio.addEventListener("focus", () => {
                lastActiveAudio = audio;
            });

            audio.addEventListener("click", () => {
                lastActiveAudio = audio;
            });
            const forwardButton = playerBlock.querySelector(".forward-btn");
            const setAButton = playerBlock.querySelector(".ab-set-a-btn");
            const setBButton = playerBlock.querySelector(".ab-set-b-btn");
            const clearABButton = playerBlock.querySelector(".ab-clear-btn");
            const abReadout = playerBlock.querySelector(".ab-readout");
            const waveformBox = playerBlock.querySelector(".waveform-box");
            const waveformImage = playerBlock.querySelector(".waveform-image");
            const abRegion = playerBlock.querySelector(".ab-region");
            const abMarkerA = playerBlock.querySelector(".ab-marker-a");
            const abMarkerB = playerBlock.querySelector(".ab-marker-b");
            const zoomReadout = playerBlock.querySelector(".zoom-readout");
            const beatCanvas = playerBlock.querySelector(".ls-player-beat-grid");
            const dynamicZoomButton = playerBlock.querySelector("#ls-global-player-zoom");
            let beatGrid = null;
            let beatToken = 0;
            let abStart = null;
            let abEnd = null;
            let zoomStart = 0;
            let zoomEnd = null;

            function syncDynamicZoomIcon(mode) {
                if (!dynamicZoomButton) { return; }
                const symbol = dynamicZoomButton.querySelector(".ls-global-player-zoom-symbol");
                let state = mode || dynamicZoomButton.dataset.zoomState || "in";
                const duration = audio.duration || 0;
                const full = duration > 0 && zoomStart <= 0.01 && (zoomEnd === null || Math.abs((zoomEnd || duration) - duration) < 0.05);
                if (full && state === "out") { state = "in"; }
                dynamicZoomButton.dataset.zoomState = state;
                if (symbol) { symbol.textContent = state === "out" ? "−" : (state === "reset" ? "↺" : "+"); }
                dynamicZoomButton.title = state === "out" ? "Zoom − · Ctrl+rullītis zoom · dubultklikšķis reset" : (state === "reset" ? "Reset zoom" : "Zoom + · Ctrl+rullītis zoom · dubultklikšķis reset");
                if (state === "reset") {
                    window.clearTimeout(dynamicZoomButton.__lsResetTimer);
                    dynamicZoomButton.__lsResetTimer = window.setTimeout(() => syncDynamicZoomIcon("in"), 850);
                }
            }

            function drawBeatGrid() {
                if (!beatCanvas) { return; }
                const rect = beatCanvas.getBoundingClientRect();
                const cssWidth = Math.max(1, Math.round(rect.width));
                const cssHeight = Math.max(1, Math.round(rect.height));
                const dpr = Math.max(1, Math.min(2.5, window.devicePixelRatio || 1));
                beatCanvas.width = Math.round(cssWidth * dpr);
                beatCanvas.height = Math.round(cssHeight * dpr);
                const ctx = beatCanvas.getContext("2d");
                if (!ctx) { return; }
                ctx.clearRect(0,0,beatCanvas.width,beatCanvas.height);
                if (!beatGrid || !(audio.duration > 0) || !(beatGrid.bpm > 0)) { return; }
                ctx.save(); ctx.scale(dpr,dpr);
                const zoom = getZoomWindow(playerBlock, audio.duration);
                const period = 60 / beatGrid.bpm;
                const first = Math.floor((zoom.start - beatGrid.offset) / period) - 1;
                const last = Math.ceil((zoom.end - beatGrid.offset) / period) + 1;
                for (let i=first;i<=last;i+=1) {
                    const t=beatGrid.offset+i*period;
                    if (t<zoom.start-period || t>zoom.end+period) continue;
                    const x=(t-zoom.start)/zoom.span*cssWidth;
                    const bar=((i%4)+4)%4===0;
                    ctx.strokeStyle=bar?"rgba(235,244,249,.22)":"rgba(235,244,249,.08)";
                    ctx.lineWidth=bar?1:.6;
                    ctx.beginPath(); ctx.moveTo(Math.round(x)+.5,0); ctx.lineTo(Math.round(x)+.5,cssHeight); ctx.stroke();
                }
                ctx.restore();
            }

            async function analyzeBeatGrid() {
                const token=++beatToken; beatGrid=null; drawBeatGrid();
                const preferred=Number(playerBlock.dataset.bpm||0)||0;
                const src=String(audio.src||"");
                if (!src) { return; }
                try {
                    const response=await fetch(src,{cache:"force-cache"});
                    if(!response.ok) return;
                    const bytes=await response.arrayBuffer();
                    const AC=window.AudioContext||window.webkitAudioContext; if(!AC) return;
                    const context=new AC();
                    try {
                        const buffer=await context.decodeAudioData(bytes.slice(0));
                        const data=buffer.getChannelData(0); const sr=buffer.sampleRate||44100; const blockSize=256; const rate=sr/blockSize; const blocks=Math.floor(data.length/blockSize);
                        if(blocks<256) return;
                        const onset=new Float32Array(blocks); let fast=0,slow=0,max=0;
                        for(let b=0;b<blocks;b++){let a=0,d=0,n=0;const st=b*blockSize,en=Math.min(data.length,st+blockSize);for(let p=st+1;p<en;p+=4){const v=data[p]||0;a+=Math.abs(v);d+=Math.abs(v-(data[p-1]||0));n++;}const raw=n?(a/n)*.72+(d/n)*2.2:0;fast=fast*.55+raw*.45;slow=slow*.94+raw*.06;const o=Math.max(0,fast-slow*.92);onset[b]=o;if(o>max)max=o;}
                        if(!(max>1e-6)) return;
                        let bpm=preferred; let lag=0;
                        if(bpm>40&&bpm<240){lag=Math.max(2,Math.round(rate*60/bpm));}
                        else {
                            const minLag=Math.floor(rate*60/190),maxLag=Math.ceil(rate*60/58);let bestScore=-1;
                            for(let l=minLag;l<=maxLag;l++){let c=0,x=0,y=0;for(let i=l;i<blocks;i++){const A=onset[i],B=onset[i-l];c+=A*B;x+=A*A;y+=B*B;}const score=c/Math.sqrt(Math.max(1e-12,x*y));if(score>bestScore){bestScore=score;lag=l;}}
                            bpm=60*rate/lag;
                        }
                        let bestPhase=0,bestScore=-1;
                        for(let phase=0;phase<lag;phase++){let score=0;for(let i=phase;i<blocks;i+=lag){score+=onset[i];if(i+1<blocks)score+=onset[i+1]*.5;if(i>0)score+=onset[i-1]*.5;}if(score>bestScore){bestScore=score;bestPhase=phase;}}
                        if(token!==beatToken)return; beatGrid={bpm,offset:bestPhase/rate}; drawBeatGrid();
                    } finally { try{await context.close();}catch(_){} }
                } catch (_) {}
            }

            function resetZoomWindow() {
                const duration = audio.duration || 0;
                zoomStart = 0;
                zoomEnd = duration || null;
                if (waveformBox) {
                    waveformBox.dataset.zoomStart = "0";
                    waveformBox.dataset.zoomEnd = String(duration || 0);
                    waveformBox.classList.remove("zoomed");
                }
                updateZoomReadout();
                drawBeatGrid();
            }

            function updateWaveformVisualZoom() {
                const duration = audio.duration || 0;
                if (!waveformImage || !duration) {
                    return;
                }
                const endValue = zoomEnd || duration;
                const span = Math.max(0.1, endValue - zoomStart);
                const zoomFactor = Math.max(1, duration / span);

                if (zoomFactor <= 1.01) {
                    waveformImage.style.width = "100%";
                    waveformImage.style.left = "0%";
                    return;
                }

                // Full waveform image is widened; left offset shows the chosen time window.
                // left percent is relative to the container width.
                const leftPct = -((zoomStart / span) * 100);
                waveformImage.style.width = (zoomFactor * 100) + "%";
                waveformImage.style.left = leftPct + "%";
            }

            function updateZoomReadout() {
                const duration = audio.duration || 0;
                if (!zoomReadout) { return; }
                updateWaveformVisualZoom();
                if (!duration || zoomStart <= 0.01 && (zoomEnd === null || Math.abs(zoomEnd - duration) < 0.05)) {
                    zoomReadout.innerText = "";
                    if (waveformBox) { waveformBox.classList.remove("zoomed"); }
                    return;
                }
                const span = Math.max(0.1, (zoomEnd || duration) - zoomStart);
                const zoomFactor = duration / span;
                zoomReadout.innerText = "Zoom ×" + zoomFactor.toFixed(1);
                if (waveformBox) { waveformBox.classList.add("zoomed"); }
            }

            function setZoomWindow(start, end) {
                const duration = audio.duration || 0;
                if (!duration) { return; }
                const minSpan = Math.min(duration, 1.0);
                zoomStart = Math.max(0, Math.min(duration - minSpan, start));
                zoomEnd = Math.max(zoomStart + minSpan, Math.min(duration, end));
                if (waveformBox) {
                    waveformBox.dataset.zoomStart = String(zoomStart);
                    waveformBox.dataset.zoomEnd = String(zoomEnd);
                }
                updateZoomReadout();
                updateProgress(playerBlock);
                updateABDisplay();
                drawBeatGrid();
            }

            function fmtShortTime(value) {
                if (!isFinite(value) || value < 0) { return "--:--"; }
                const m = Math.floor(value / 60);
                const s = Math.floor(value % 60);
                return String(m) + ":" + String(s).padStart(2, "0");
            }

            function updateABDisplay() {
                const duration = audio.duration || 0;
                const hasA = abStart !== null && isFinite(abStart);
                const hasB = abEnd !== null && isFinite(abEnd);

                if (setAButton) { setAButton.classList.toggle("active", hasA); }
                if (setBButton) { setBButton.classList.toggle("active", hasB); }
                if (clearABButton) { clearABButton.disabled = !(hasA || hasB); }

                if (abMarkerA) {
                    if (hasA && duration > 0) {
                        abMarkerA.style.left = timeToZoomPercent(playerBlock, abStart) + "%";
                        abMarkerA.style.display = "block";
                    } else {
                        abMarkerA.style.display = "none";
                    }
                }

                if (abMarkerB) {
                    if (hasB && duration > 0) {
                        abMarkerB.style.left = timeToZoomPercent(playerBlock, abEnd) + "%";
                        abMarkerB.style.display = "block";
                    } else {
                        abMarkerB.style.display = "none";
                    }
                }

                if (abRegion) {
                    if (hasA && hasB && duration > 0 && abEnd > abStart) {
                        const left = timeToZoomPercent(playerBlock, abStart);
                        const right = timeToZoomPercent(playerBlock, abEnd);
                        abRegion.style.left = left + "%";
                        abRegion.style.width = Math.max(0, right - left) + "%";
                        abRegion.style.display = "block";
                    } else {
                        abRegion.style.display = "none";
                    }
                }

                if (abReadout) {
                    if (hasA && hasB && abEnd > abStart) {
                        abReadout.innerText = "A/B " + fmtShortTime(abStart) + "–" + fmtShortTime(abEnd);
                    } else if (hasA) {
                        abReadout.innerText = "A " + fmtShortTime(abStart);
                    } else if (hasB) {
                        abReadout.innerText = "B " + fmtShortTime(abEnd);
                    } else {
                        abReadout.innerText = "";
                    }
                }
            }

            function setABPoint(which) {
                if (!audio || !isFinite(audio.currentTime)) { return; }
                const t = Math.max(0, audio.currentTime || 0);
                if (which === "a") {
                    abStart = t;
                    if (abEnd !== null && abEnd <= abStart) { abEnd = null; }
                } else {
                    abEnd = t;
                    if (abStart !== null && abEnd <= abStart) {
                        const oldA = abStart;
                        abStart = abEnd;
                        abEnd = oldA;
                    }
                }
                updateABDisplay();
            }

            playerBlock.classList.remove("hidden");
            audio.src = audioSrc;
            audio.loop = false;
            abStart = null;
            abEnd = null;
            resetZoomWindow();
            updateABDisplay();
            const loopButton = playerBlock.querySelector(".loop-audio-btn");
            if (loopButton) {
                loopButton.classList.remove("active");
                loopButton.innerText = "Loop";
                loopButton.title = "Loop: atskaņot šo audio bezgalīgi";
            }
            audio.load();

            loadWaveform(playerBlock, trackId, waveformSource);

            audio.onloadedmetadata = () => {
                resetZoomWindow();
                updateProgress(playerBlock);
                updateABDisplay();
                analyzeBeatGrid();
            };

            audio.ontimeupdate = () => {
                updateProgress(playerBlock);
                if (audio.loop && abStart !== null && abEnd !== null && abEnd > abStart) {
                    if (audio.currentTime >= abEnd || audio.currentTime < abStart) {
                        audio.currentTime = abStart;
                        audio.play().catch(() => {});
                    }
                }
            };

            audio.onended = () => {
                if (audio.loop && abStart !== null && abEnd !== null && abEnd > abStart) {
                    audio.currentTime = abStart;
                    audio.play().catch(() => {});
                    return;
                }
                if (endCallback) {
                    endCallback();
                }
                updateProgress(playerBlock);
            };

            if (setAButton) {
                setAButton.onclick = () => setABPoint("a");
            }

            if (setBButton) {
                setBButton.onclick = () => setABPoint("b");
            }

            if (clearABButton) {
                clearABButton.onclick = () => {
                    abStart = null;
                    abEnd = null;
                    updateABDisplay();
                };
            }

            if (backButton) {
                backButton.onclick = () => {
                    audio.currentTime = Math.max(0, audio.currentTime - 10);
                    updateProgress(playerBlock);
                };
            }

            if (forwardButton) {
                forwardButton.onclick = () => {
                    if (audio.duration) {
                        audio.currentTime = Math.min(audio.duration, audio.currentTime + 10);
                        updateProgress(playerBlock);
                    }
                };
            }

            waveformBox.onclick = (event) => {
                const rect = waveformBox.getBoundingClientRect();
                const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));

                if (audio.duration) {
                    audio.currentTime = zoomPercentToTime(playerBlock, ratio);
                    if (event.ctrlKey || event.shiftKey) {
                        setABPoint("a");
                    } else if (event.altKey) {
                        setABPoint("b");
                    }
                    updateProgress(playerBlock);
                }
            };

            waveformBox.addEventListener("wheel", (event) => {
                if (!audio.duration) { return; }

                // Normal mouse wheel must not zoom or move anything.
                // Zoom is only Ctrl + mouse wheel over waveform.
                if (!event.ctrlKey) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const rect = waveformBox.getBoundingClientRect();
                const pct = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
                const zoom = getZoomWindow(playerBlock, audio.duration);
                const center = zoom.start + pct * zoom.span;
                const factor = event.deltaY < 0 ? 0.72 : 1.38;
                let newSpan = Math.max(0.5, Math.min(audio.duration, zoom.span * factor));
                let start = center - pct * newSpan;
                let end = start + newSpan;
                if (start < 0) {
                    end -= start;
                    start = 0;
                }
                if (end > audio.duration) {
                    start -= (end - audio.duration);
                    end = audio.duration;
                }
                setZoomWindow(start, end);
                syncDynamicZoomIcon(event.deltaY < 0 ? "in" : "out");
            }, { passive: false });

            waveformBox.ondblclick = (event) => {
                event.preventDefault();
                resetZoomWindow();
                updateProgress(playerBlock);
                updateABDisplay();
                syncDynamicZoomIcon("reset");
            };

            if (dynamicZoomButton) {
                dynamicZoomButton.onclick = (event) => {
                    event.preventDefault();
                    if (!audio.duration) { return; }
                    const state=dynamicZoomButton.dataset.zoomState||"in";
                    const z=getZoomWindow(playerBlock,audio.duration);
                    if(state==="reset"){resetZoomWindow();updateProgress(playerBlock);updateABDisplay();syncDynamicZoomIcon("reset");return;}
                    const factor=state==="out"?1.62:.62;
                    const center=(audio.currentTime>=z.start&&audio.currentTime<=z.end)?audio.currentTime:(z.start+z.end)/2;
                    let span=Math.max(.5,Math.min(audio.duration,z.span*factor));
                    if(span>=audio.duration-.05){resetZoomWindow();syncDynamicZoomIcon("reset");updateProgress(playerBlock);updateABDisplay();return;}
                    let start=center-span/2,end=start+span;if(start<0){end-=start;start=0;}if(end>audio.duration){start-=end-audio.duration;end=audio.duration;}
                    setZoomWindow(start,end);syncDynamicZoomIcon(state==="out"?"out":"in");
                };
                dynamicZoomButton.ondblclick = (event) => { event.preventDefault(); resetZoomWindow(); updateProgress(playerBlock); updateABDisplay(); syncDynamicZoomIcon("reset"); };
            }

            function makeABMarkerDraggable(node, which) {
                if (!node || !waveformBox) return;
                let pointer=null;
                const move=(event)=>{if(pointer!==event.pointerId)return;const rect=waveformBox.getBoundingClientRect();if(!audio.duration||!rect.width)return;const ratio=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));const value=zoomPercentToTime(playerBlock,ratio);if(which==="a"){const hi=abEnd!==null?Math.max(0,abEnd-.05):audio.duration;abStart=Math.max(0,Math.min(value,hi));}else{const lo=abStart!==null?abStart+.05:0;abEnd=Math.max(lo,Math.min(value,audio.duration));}updateABDisplay();event.preventDefault();};
                const done=(event)=>{if(pointer!==event.pointerId)return;pointer=null;try{node.releasePointerCapture(event.pointerId);}catch(_){} event.preventDefault();};
                node.onpointerdown=(event)=>{if((which==="a"?abStart:abEnd)===null)return;pointer=event.pointerId;try{node.setPointerCapture(pointer);}catch(_){} move(event);event.stopPropagation();};
                node.onpointermove=move;node.onpointerup=done;node.onpointercancel=done;
            }
            makeABMarkerDraggable(abMarkerA,"a");
            makeABMarkerDraggable(abMarkerB,"b");

            return audio;
        }
