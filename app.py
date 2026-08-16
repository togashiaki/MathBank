# TRANG 4: MỤC LỤC & SƠ ĐỒ DẠNG BÀI (THEO DÕI SỐ LƯỢNG CÂU HỎI - ACCORDION THU GỌN)
elif st.session_state["current_nav_tab"] == "📚":
    # 1. Thu thập và tính toán dữ liệu thống kê từ Excel + Google Sheets
    base_tax_structure = get_taxonomy_structure()
    
    full_toc_data = {}
    grade_totals = {"12": 0, "11": 0, "10": 0, "HSA": 0}
    
    for g_key in ["12", "11", "10", "HSA"]:
        full_toc_data[g_key] = {}
        if g_key in base_tax_structure:
            for c_num, c_info in base_tax_structure[g_key].items():
                full_toc_data[g_key][c_num] = {
                    'title': c_info['title'],
                    'topics': {t: 0 for t in c_info['topics']}
                }

    for q in all_questions:
        g = str(q.grade).strip()
        try:
            c = int(q.chapter)
        except (ValueError, TypeError):
            c = 1
        t = str(q.topic).strip() if q.topic else "Chưa phân dạng"

        if g not in full_toc_data:
            full_toc_data[g] = {}
            grade_totals[g] = 0

        grade_totals[g] = grade_totals.get(g, 0) + 1

        if c not in full_toc_data[g]:
            full_toc_data[g][c] = {
                'title': f"Chương {c}",
                'topics': {}
            }

        if t not in full_toc_data[g][c]['topics']:
            full_toc_data[g][c]['topics'][t] = 0

        full_toc_data[g][c]['topics'][t] += 1

    # 2. Bố cục 2 cột (Cột trái: Mục lục & chọn Khối lớp; Cột phải: Chi tiết các chương thu gọn)
    col_toc_nav, col_toc_content = st.columns([1, 2.8])

    with col_toc_nav:
        st.markdown("<div style='font-size: 1.75rem; font-weight: 800; color: #2c2825; margin-bottom: 14px;'>Mục lục</div>", unsafe_allow_html=True)
        toc_search = st.text_input("Tìm kiếm dạng bài...", "", key="toc_search_input", placeholder="🔍 cực trị, tiệm cận, xác suất...")

        st.markdown("<div style='margin-top: 16px; margin-bottom: 8px; font-weight: 700; color: #78716c; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;'>Khối lớp</div>", unsafe_allow_html=True)
        
        grade_labels = {
            "12": "Toán 12",
            "11": "Toán 11",
            "10": "Toán 10",
            "HSA": "HSA / ĐGNL"
        }

        active_grade = st.session_state.get("toc_selected_grade", "12")
        for g_code in ["12", "11", "10", "HSA"]:
            g_count = grade_totals.get(g_code, 0)
            is_cur_g = (active_grade == g_code)
            
            btn_text = f"{grade_labels.get(g_code, g_code)}   ({g_count} câu)"
            if st.button(btn_text, key=f"btn_toc_grade_{g_code}", type="primary" if is_cur_g else "secondary", width="stretch"):
                st.session_state["toc_selected_grade"] = g_code
                st.rerun()

    with col_toc_content:
        cur_grade = st.session_state.get("toc_selected_grade", "12")
        grade_display = grade_labels.get(cur_grade, f"Toán {cur_grade}")
        cur_grade_total = grade_totals.get(cur_grade, 0)

        st.markdown(
            f'<div style="display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #b8543f; padding-bottom: 8px; margin-bottom: 20px;">'
            f'<span style="font-size: 1.5rem; font-weight: 800; color: #2c2825;">{grade_display}</span>'
            f'<span style="font-size: 0.95rem; font-weight: 700; color: #78716c;">Tổng cộng: <b style="color: #b8543f; font-family: \'JetBrains Mono\', monospace;">{cur_grade_total}</b> câu</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        grade_chapters = full_toc_data.get(cur_grade, {})
        search_kw = toc_search.strip().lower()

        rendered_chapters_count = 0
        sorted_chaps = sorted(grade_chapters.keys(), key=lambda x: int(x) if str(x).isdigit() else 99)

        for c_idx in sorted_chaps:
            c_data = grade_chapters[c_idx]
            c_title = c_data['title']
            all_c_topics = c_data['topics']

            # Lọc theo từ khóa tìm kiếm
            if search_kw:
                filtered_topics = {t: cnt for t, cnt in all_c_topics.items() if search_kw in t.lower() or search_kw in c_title.lower()}
                is_open_attr = "open"  # Mở chương khi có từ khóa tìm kiếm
            else:
                filtered_topics = all_c_topics
                is_open_attr = ""      # Mặc định thu gọn

            if not filtered_topics and search_kw:
                continue

            rendered_chapters_count += 1
            chap_total_qs = sum(all_c_topics.values())

            # Ghép chuỗi HTML không khoảng trắng thụt lề để tránh Markdown code-block
            topic_rows = []
            for top_name, top_cnt in filtered_topics.items():
                zero_cls = " zero" if top_cnt == 0 else ""
                topic_rows.append(
                    f'<div class="toc-item-row">'
                    f'<span class="toc-item-name">{top_name}</span>'
                    f'<div class="toc-item-dots"></div>'
                    f'<span class="toc-item-count{zero_cls}">{top_cnt}</span>'
                    f'</div>'
                )
            rows_html = "".join(topic_rows)

            chapter_html = (
                f'<details class="toc-details-card" {is_open_attr}>'
                f'<summary class="toc-summary">'
                f'<span class="toc-chap-title"><span class="toc-chevron">▶</span>{c_title}</span>'
                f'<span class="toc-chap-badge">{chap_total_qs} câu</span>'
                f'</summary>'
                f'<div class="toc-content-body">'
                f'<div class="toc-grid">{rows_html}</div>'
                f'</div>'
                f'</details>'
            )

            st.markdown(chapter_html, unsafe_allow_html=True)

        if rendered_chapters_count == 0:
            if search_kw:
                st.info(f"Không tìm thấy dạng bài nào khớp với từ khóa **'{toc_search}'** trong {grade_display}.")
            else:
                st.info(f"Chưa có dữ liệu phân loại hoặc câu hỏi cho khối {grade_display}.")
