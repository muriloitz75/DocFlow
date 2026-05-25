# -*- coding: utf-8 -*-
"""Testes leves da interface Flask, sem dependência de pytest."""

import io
import os
import unittest
import unittest.mock

import app as webapp


class WebInterfaceTestCase(unittest.TestCase):
    def setUp(self):
        upload_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_uploads")
        os.makedirs(upload_root, exist_ok=True)
        webapp.app.config["TESTING"] = True
        webapp.app.config["UPLOAD_FOLDER"] = upload_root
        self.client = webapp.app.test_client()

    def post_file(self, content, filename, option="standard"):
        return self.client.post(
            "/api/convert",
            data={
                "file": (io.BytesIO(content), filename),
                "option": option,
            },
            content_type="multipart/form-data",
        )

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")
        self.assertIn("pdf", response.json["formats"])

    def test_convert_requires_file(self):
        response = self.client.post("/api/convert", data={})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["success"])

    def test_rejects_unknown_extension(self):
        response = self.post_file(b"not allowed", "sample.exe")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Formato não suportado", response.json["error"])

    def test_converts_json_file(self):
        response = self.post_file(b'{"project":"MarkItDown"}', "sample.json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIn("MarkItDown", response.json["content"])

    def test_compact_markdown_removes_repeated_blank_lines(self):
        content = "Linha 1\n\n\nLinha 2\n"

        self.assertEqual(webapp.compact_markdown(content), "Linha 1\n\nLinha 2")

    def test_abnt_markdown_numbers_and_uppercases_headings(self):
        content = "# Introdução\n\n## Objetivo geral\n\nTexto."

        result = webapp.normalize_abnt_markdown(content)

        self.assertIn("# 1 INTRODUÇÃO", result)
        self.assertIn("## 1.1 OBJETIVO GERAL", result)

    def test_abnt_markdown_promotes_legal_headings(self):
        content = "LIVRO I\nDOS TRIBUTOS\nTÍTULO I\nCAPÍTULO I\nSeção I\nTexto."

        result = webapp.normalize_abnt_markdown(content)

        self.assertIn("# 1 LIVRO I", result)
        self.assertIn("## 1.1 TÍTULO I", result)
        self.assertIn("### 1.1.1 CAPÍTULO I", result)
        self.assertIn("#### 1.1.1.1 SEÇÃO I", result)

    def test_pdf_cleanup_removes_repeated_header_and_footer(self):
        content = (
            "RELATORIO OFICIAL\n"
            "Conteudo importante da primeira pagina.\n"
            "Pagina 1 de 2\f"
            "RELATORIO OFICIAL\n"
            "Conteudo importante da segunda pagina.\n"
            "Pagina 2 de 2"
        )

        result = webapp.clean_pdf_headers_footers(content)

        self.assertNotIn("RELATORIO OFICIAL", result)
        self.assertNotIn("Pagina 1 de 2", result)
        self.assertNotIn("Pagina 2 de 2", result)
        self.assertIn("Conteudo importante da primeira pagina.", result)
        self.assertIn("Conteudo importante da segunda pagina.", result)

    def test_pdf_cleanup_removes_standalone_page_numbers(self):
        content = "Introducao\n\n1\n\nDesenvolvimento"

        result = webapp.clean_pdf_headers_footers(content)

        self.assertEqual(result, "Introducao\n\nDesenvolvimento")

    def test_pdf_cleanup_removes_repeated_margin_noise_without_page_breaks(self):
        content = "\n".join([
            "Divisão de Arrecadação, Auditoria e Fiscalização - DIAAF",
            "Texto da pagina 1",
            "Divisão de Arrecadação, Auditoria e Fiscalização - DIAAF",
            "Texto da pagina 2",
            "Divisão de Arrecadação, Auditoria e Fiscalização - DIAAF",
            "Texto da pagina 3",
            "Divisão de Arrecadação, Auditoria e Fiscalização - DIAAF",
            "Texto da pagina 4",
            "Divisão de Arrecadação, Auditoria e Fiscalização - DIAAF",
            "Texto da pagina 5",
        ])

        result = webapp.clean_pdf_headers_footers(content)

        self.assertNotIn("DIAAF", result)
        self.assertIn("Texto da pagina 1", result)
        self.assertIn("Texto da pagina 5", result)

    def test_pdf_cleanup_removes_known_diaaf_header_even_once(self):
        content = "\n".join([
            "Texto anterior",
            "Divisão de Arrecadação, Auditoria e Fiscalização - DIAAF",
            "Texto posterior",
        ])

        result = webapp.clean_pdf_headers_footers(content)

        self.assertNotIn("DIAAF", result)
        self.assertEqual(result, "Texto anterior\nTexto posterior")

    def test_pdf_cleanup_removes_diaaf_header_embedded_in_line(self):
        content = "Texto anterior Divisão de Arrecadação, Auditoria e Fiscalização - DIAAF Texto posterior"

        result = webapp.clean_pdf_headers_footers(content)

        self.assertNotIn("DIAAF", result)
        self.assertEqual(result, "Texto anterior Texto posterior")

    def test_pdf_cleanup_removes_duplicate_document_restart(self):
        content = (
            "DECRETO Nº 019 DE 30 DE MARÇO DE 2023.\n"
            "Texto A\nTexto B\nTexto C\n"
            "GABINETE DO PREFEITO MUNICIPAL DE IMPERATRIZ\n"
            "DECRETO Nº 019 DE 30 DE MARÇO DE 2023.\n"
            "Texto A\nTexto B\nTexto C\n"
            "GABINETE DO PREFEITO MUNICIPAL DE IMPERATRIZ\n"
        )

        result = webapp.clean_pdf_headers_footers(content)

        self.assertEqual(result.count("DECRETO Nº 019"), 1)

    def test_model2_combines_legal_heading_with_descriptor(self):
        content = "LIVRO I\nDOS TRIBUTOS MUNICIPAIS\nTexto inicial."

        result = webapp.format_pdf_markdown_model2(content)

        self.assertIn("# LIVRO I - DOS TRIBUTOS MUNICIPAIS", result)

    def test_model2_removes_generated_heading_numbers(self):
        content = "# 1 LIVRO I\nDOS TRIBUTOS MUNICIPAIS\n## 1.1 TÍTULO I"

        result = webapp.format_pdf_markdown_model2(content)

        self.assertIn("# LIVRO I - DOS TRIBUTOS MUNICIPAIS", result)
        self.assertIn("## TÍTULO I", result)
        self.assertNotIn("# 1 LIVRO I", result)

    def test_model2_bolds_article_opening(self):
        content = "Art.1º. Este decreto regulamenta a lei municipal."

        result = webapp.format_pdf_markdown_model2(content)

        self.assertIn("**Art. 1º** Este decreto regulamenta a lei municipal.", result)

    def test_model2_reflows_wrapped_pdf_paragraphs(self):
        content = (
            "Art. 2º. O sujeito passivo da obrigação tributária\n"
            "deverá observar os prazos previstos neste regulamento\n"
            "e manter a documentação organizada."
        )

        result = webapp.format_pdf_markdown_model2(content)

        self.assertIn(
            "**Art. 2º** O sujeito passivo da obrigação tributária deverá observar "
            "os prazos previstos neste regulamento e manter a documentação organizada.",
            result,
        )

    def test_model2_polish_strips_abnt_heading_numbers(self):
        content = "# 1 LIVRO I - DOS TRIBUTOS\n\n## 1.1 TÍTULO I - DISPOSIÇÕES GERAIS"

        result = webapp.polish_legal_markdown_model2(content)

        self.assertIn("# LIVRO I - DOS TRIBUTOS", result)
        self.assertIn("## TÍTULO I - DISPOSIÇÕES GERAIS", result)
        self.assertNotIn("# 1 LIVRO", result)

    def test_model2_polish_merges_heading_descriptor_after_blank(self):
        content = "## 1.2 TÍTULO II - DO IMPOSTO SOBRE A PROPRIEDADE PREDIAL E TERRITORIAL URBANA\n\nIPTU"

        result = webapp.polish_legal_markdown_model2(content)

        self.assertIn(
            "## TÍTULO II - DO IMPOSTO SOBRE A PROPRIEDADE PREDIAL E TERRITORIAL URBANA - IPTU",
            result,
        )
        self.assertNotRegex(result, r"(?m)^IPTU$")

    def test_model2_polish_splits_official_clauses(self):
        content = (
            "Aprova o Regulamento e dá outras providências. FRANCISCO DE ASSIS ANDRADE RAMOS, "
            "Prefeito Municipal, DECRETA:"
        )

        result = webapp.polish_legal_markdown_model2(content)

        self.assertIn("providências.\n\nFRANCISCO DE ASSIS", result)

    def test_model2_polish_merges_spurious_continuation_break(self):
        content = "**§ 2º** A atribuição pode ser revogada, a qualquer tempo, por ato\n\nunilateral do Município."

        result = webapp.polish_legal_markdown_model2(content)

        self.assertIn("por ato unilateral do Município.", result)

    def test_model2_polish_keeps_regulation_title_separate_from_signature(self):
        content = (
            "FRANCISCO DE ASSIS ANDRADE RAMOS PREFEITO MUNICIPAL\n\n"
            "REGULAMENTO DA Lei Complementar nº 005 DE 30 DE DEZEMBRO DE 2022."
        )

        result = webapp.polish_legal_markdown_model2(content)

        self.assertIn("PREFEITO MUNICIPAL\n\nREGULAMENTO", result)

    def test_model2_polish_repairs_known_decree_dislocation(self):
        content = (
            "Sempre que possível, os impostos terão caráter pessoal e serão graduados segundo a "
            "capacidade econômica do Tributária, especialmente para conferir efetividade a esses "
            "objetivos, identificar, nos termos da lei e respeitados os direitos individuais, o "
            "patrimônio, os rendimentos e as atividades econômicas do contribuinte.\n\n"
            "contribuinte,\n\nAdministração\n\nfacultado\n\nà"
        )

        result = webapp.polish_legal_markdown_model2(content)

        self.assertIn(
            "capacidade econômica do contribuinte, facultado à Administração Tributária",
            result,
        )
        self.assertNotIn("econômica do Tributária", result)

    def test_strip_generated_heading_number_with_dot(self):
        self.assertEqual(webapp._strip_generated_heading_number("1. Introdução"), "Introdução")
        self.assertEqual(webapp._strip_generated_heading_number("1.1. Objetivos"), "Objetivos")
        self.assertEqual(webapp._strip_generated_heading_number("1 Introdução"), "Introdução")

    def test_normalize_abnt_markdown_preserves_already_numbered_headings(self):
        content = "# 1 Introdução\n\n## 1.1 Objetivo Geral\n\nTexto."
        result = webapp.normalize_abnt_markdown(content)
        self.assertEqual(result, "# 1 INTRODUÇÃO\n\n## 1.1 OBJETIVO GERAL\n\nTexto.")

    def test_secure_filename_preserves_non_ascii_extensions(self):
        response = self.post_file(b"Texto simples de teste", "документ.txt")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertTrue(response.json["filename"].endswith(".txt"))

    def test_is_sentencecase_descriptor_detects_sentence_case_descriptors(self):
        self.assertTrue(webapp._is_sentencecase_descriptor("Da inscrição e alteração cadastral"))
        self.assertTrue(webapp._is_sentencecase_descriptor("Do recolhimento do ISSQN"))
        self.assertFalse(webapp._is_sentencecase_descriptor("Art. 58. Ficam obrigados"))
        self.assertFalse(webapp._is_sentencecase_descriptor("§ 1º Para fins de recolhimento"))
        self.assertFalse(webapp._is_sentencecase_descriptor("Este é um parágrafo normal que termina com ponto."))

    def test_model2_combines_legal_heading_with_sentence_case_descriptor(self):
        content = "SEÇÃO II\nDa inscrição e alteração cadastral\nArt. 58. Ficam obrigados."
        result = webapp.format_pdf_markdown_model2(content)
        self.assertIn("#### SEÇÃO II - Da inscrição e alteração cadastral", result)

    def test_model2_combines_legal_heading_with_long_sentence_case_descriptor_no_blank_line(self):
        content = (
            "SUBSEÇÃO I\n"
            "Da Nota Fiscal de Serviços Eletrônica (NFS-e), do Recibo Provisório de Serviços (RPS), "
            "da Nota Fiscal de Fatura (NFF) e do Cupom Fiscal de Serviços eletrônico (CFS-e)\n"
            "Art. 65. A Nota Fiscal de Serviços..."
        )
        result = webapp.format_pdf_markdown_model2(content)
        self.assertIn(
            "##### SUBSEÇÃO I - Da Nota Fiscal de Serviços Eletrônica (NFS-e), do Recibo Provisório de Serviços (RPS), "
            "da Nota Fiscal de Fatura (NFF) e do Cupom Fiscal de Serviços eletrônico (CFS-e)",
            result
        )

    def test_model2_combines_legal_heading_with_long_sentence_case_descriptor_with_blank_line(self):
        content = (
            "SUBSEÇÃO I\n\n"
            "Da Nota Fiscal de Serviços Eletrônica (NFS-e), do Recibo Provisório de Serviços (RPS), "
            "da Nota Fiscal de Fatura (NFF) e do Cupom Fiscal de Serviços eletrônico (CFS-e)\n\n"
            "Art. 65. A Nota Fiscal de Serviços..."
        )
        result = webapp.format_pdf_markdown_model2(content)
        self.assertIn(
            "##### SUBSEÇÃO I - Da Nota Fiscal de Serviços Eletrônica (NFS-e), do Recibo Provisório de Serviços (RPS), "
            "da Nota Fiscal de Fatura (NFF) e do Cupom Fiscal de Serviços eletrônico (CFS-e)",
            result
        )

    def test_model2_combines_legal_heading_with_multiline_descriptor(self):
        content = (
            "SUBSEÇÃO I\n"
            "Da Nota Fiscal de Serviços Eletrônica (NFS-e), do Recibo Provisório de Serviços (RPS), da\n"
            "Nota Fiscal de Fatura (NFF) e do Cupom Fiscal de Serviços eletrônico (CFS-e)\n"
            "Art. 65. A Nota Fiscal de Serviços..."
        )
        result = webapp.format_pdf_markdown_model2(content)
        self.assertIn(
            "##### SUBSEÇÃO I - Da Nota Fiscal de Serviços Eletrônica (NFS-e), do Recibo Provisório de Serviços (RPS), da "
            "Nota Fiscal de Fatura (NFF) e do Cupom Fiscal de Serviços eletrônico (CFS-e)",
            result
        )

    def test_large_file_error_handler_message(self):
        old_limit = webapp.app.config.get("MAX_CONTENT_LENGTH")
        webapp.app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
        try:
            with webapp.app.app_context():
                response = webapp.handle_large_file(None)
                data = response[0].get_json()
                self.assertEqual(response[1], 413)
                self.assertIn("limite atual é 200 MB", data["error"])
        finally:
            if old_limit is not None:
                webapp.app.config["MAX_CONTENT_LENGTH"] = old_limit

    @unittest.mock.patch("requests.get")
    def test_convert_via_url_success(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html><body><h1>DocFlow</h1><p>Teste por URL.</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.post(
            "/api/convert",
            data={
                "url": "https://exemplo.com/documento.html",
                "option": "standard",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIn("DocFlow", response.json["content"])
        self.assertEqual(response.json["filename"], "documento.html")
        mock_get.assert_called_once_with(
            "https://exemplo.com/documento.html",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=15
        )

    @unittest.mock.patch("requests.get")
    def test_convert_via_url_auto_prepend_protocol(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html><body><h1>DocFlow Protocol-less</h1></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.post(
            "/api/convert",
            data={
                "url": "www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
                "option": "standard",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIn("DocFlow Protocol-less", response.json["content"])
        self.assertEqual(response.json["filename"], "l5172compilado.htm")
        mock_get.assert_called_once_with(
            "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=15
        )

    @unittest.mock.patch("requests.get")
    def test_convert_via_htm_url_keeps_content_after_premature_body_close(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.content = (
            b"<html><body><p>Parte dentro do body.</p></body>"
            b"<p>Parte depois do body que tambem pertence ao documento.</p></html>"
        )
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.post(
            "/api/convert",
            data={
                "url": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
                "option": "standard",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIn("Parte dentro do body.", response.json["content"])
        self.assertIn("Parte depois do body que tambem pertence ao documento.", response.json["content"])

    def test_html_decoder_keeps_valid_utf8_even_when_default_encoding_is_wrong(self):
        raw = (
            "<html><body>Presid\u00eancia da Rep\u00fablica "
            "C\u00f3digo Tribut\u00e1rio Nacional</body></html>"
        ).encode("utf-8")

        text, encoding = webapp.decode_html_bytes(raw, default_encoding="cp1251")

        self.assertEqual(encoding, "utf-8")
        self.assertIn("Presid\u00eancia da Rep\u00fablica", text)
        self.assertIn("C\u00f3digo Tribut\u00e1rio Nacional", text)
        self.assertNotIn("\u0413", text)

    def test_html_decoder_uses_cp1252_for_legacy_planalto_pages(self):
        raw = (
            "<html><body>Presid\u00eancia da Rep\u00fablica "
            "C\u00f3digo Tribut\u00e1rio Nacional</body></html>"
        ).encode("cp1252")

        text, encoding = webapp.decode_html_bytes(raw, prefer_cp1252=True)

        self.assertEqual(encoding, "cp1252")
        self.assertIn("Presid\u00eancia da Rep\u00fablica", text)
        self.assertIn("C\u00f3digo Tribut\u00e1rio Nacional", text)

    @unittest.mock.patch("requests.get")
    def test_convert_via_url_does_not_turn_utf8_accents_into_cyrillic_mojibake(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.encoding = "cp1251"
        mock_response.content = (
            "<html><head></head><body>"
            "<p>Presid\u00eancia da Rep\u00fablica Casa Civil Subchefia para Assuntos Jur\u00eddicos</p>"
            "<p>LEI N\u00ba 5.172, DE 25 DE OUTUBRO DE 1966.</p>"
            "<p>Denominado C\u00f3digo Tribut\u00e1rio Nacional. Produ\u00e7\u00e3o de efeitos.</p>"
            "<p>O PRESIDENTE DA REP\u00daBLICA Fa\u00e7o saber que o Congresso Nacional decreta.</p>"
            "</body></html>"
        ).encode("utf-8")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.post(
            "/api/convert",
            data={
                "url": "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
                "option": "standard",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIn("Rep\u00fablica", response.json["content"])
        self.assertIn("C\u00f3digo Tribut\u00e1rio", response.json["content"])
        self.assertNotIn("\u0413", response.json["content"])
        self.assertNotIn("\u0412", response.json["content"])

    def test_planalto_split_does_not_treat_lowercase_congress_continuation_as_promulgation(self):
        content = "\n".join([
            "Constituição",
            "",
            "| Presidência da República |",
            "",
            "**PREÂMBULO**",
            "",
            "**TÍTULO I**",
            "",
            "Art. 224. Para os efeitos do disposto neste capítulo,",
            "o Congresso Nacional instituirá o Conselho de Comunicação Social.",
            "",
            "CAPÍTULO VI",
            "",
            "DO MEIO AMBIENTE",
        ])

        header_text, body_text = webapp.split_planalto_document(content)

        self.assertNotIn("Art. 224", header_text)
        self.assertIn("**PREÂMBULO**", body_text)
        self.assertIn("o Congresso Nacional instituirá", body_text)

    def test_planalto_split_constitution_starts_body_at_preamble(self):
        content = "\n".join([
            "Constituição",
            "",
            "| Presidência da República |",
            "",
            "**CONSTITUIÇÃO DA REPÚBLICA FEDERATIVA DO BRASIL DE 1988**",
            "",
            "**PREÂMBULO**",
            "",
            "**TÍTULO I**",
            "",
            "Art. 1º A República Federativa do Brasil...",
            "",
            "> **ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS**",
            "",
            "Art. 1º. O Presidente da República, o Presidente do Supremo Tribunal Federal e os",
            "membros do Congresso Nacional prestarão o compromisso.",
        ])

        header_text, body_text = webapp.split_planalto_document(content)

        self.assertIn("CONSTITUIÇÃO DA REPÚBLICA", header_text)
        self.assertNotIn("**PREÂMBULO**", header_text)
        self.assertTrue(body_text.startswith("**PREÂMBULO**"))
        self.assertIn("O Presidente da República", body_text)

    @unittest.mock.patch("requests.get")
    def test_convert_via_url_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection timed out")

        response = self.client.post(
            "/api/convert",
            data={
                "url": "https://exemplo-com-erro.com/doc.html",
                "option": "standard",
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["success"])
        self.assertIn("Erro ao baixar a URL", response.json["error"])

    def test_convert_via_url_invalid(self):
        response = self.client.post(
            "/api/convert",
            data={
                "url": "ftp://link-invalido.com",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["success"])
        self.assertIn("URL inválida", response.json["error"])

    def test_citation_protection_does_not_format_references(self):
        content = (
            "Esta Lei regula, com fundamento na Emenda Constitucional n. 18, de 1º de dezembro de 1965, "
            "o sistema tributário nacional e estabelece, com fundamento no\n\n"
            "Art. 5º, inciso XV, alínea b, da Constituição Federal as normas gerais de direito tributário"
        )
        result = webapp.format_pdf_markdown_model2(content)
        self.assertNotIn("**Art. 5º**", result)
        self.assertIn("no Art. 5º, inciso XV", result)

    def test_citation_protection_with_semicolon(self):
        content = (
            "houver descumprimento reiterado da obrigação contida no inciso I do caput do\n\n"
            "Art. 26.;\n"
            "o limite proporcional de receita bruta de que trata o § 2o do\n\n"
            "Art. 3o;"
        )
        result = webapp.format_pdf_markdown_model2(content)
        self.assertNotIn("**Art. 26.**", result)
        self.assertNotIn("**Art. 3º**", result)
        self.assertNotIn("**Art. 3o**", result)
        self.assertIn("do Art. 26.;", result)
        self.assertIn("do Art. 3o;", result)

    def test_model2_does_not_merge_structural_elements_after_parenthesis(self):
        content = (
            "cobrar impostos e a contribuição de que trata o inciso V do art. 195 da Constituição Federalsobre: (Redação dada pela Lei Complementar nº 214, de 2025) Produção de efeitos\n\n"
            "c)o patrimônio, a renda ou serviços dos partidos políticos..."
        )
        result = webapp.format_pdf_markdown_model2(content)
        self.assertIn("c)o patrimônio", result)

    def test_inline_structural_element_splitting(self):
        content = (
            "Art. 18-A. Para fins da incidência do imposto de que trata o inciso II do caput do art. 155 da "
            "Constituição Federal, os combustíveis... (Incluído pela Lei Complementar nº 194, de 2022) "
            "Parágrafo único. Para efeito do disposto neste artigo:"
        )
        result = webapp.format_pdf_markdown_model2(content)
        self.assertIn("**Parágrafo único.** Para efeito", result)

    def test_saved_documents_lifecycle(self):
        # 1. Salvar um documento
        doc_data = {
            "html": "<p>Conteúdo HTML</p>",
            "markdown": "Conteúdo Markdown",
            "filename": "teste_doc.pdf",
            "mode": "standard"
        }
        response = self.client.post(
            "/api/saved_docs",
            json=doc_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        doc_id = response.json["id"]
        self.assertTrue(doc_id.startswith("teste_doc"))

        # 2. Listar documentos salvos
        response = self.client.get("/api/saved_docs")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        docs = response.json["documents"]
        self.assertTrue(any(d["id"] == doc_id for d in docs))

        # 3. Pegar o documento específico
        response = self.client.get(f"/api/saved_docs/{doc_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["document"]["markdown"], "Conteúdo Markdown")

        # 4. Excluir o documento
        response = self.client.delete(f"/api/saved_docs/{doc_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["message"], "Documento excluído com sucesso.")

        # 5. Tentar pegar novamente e receber 404
        response = self.client.get(f"/api/saved_docs/{doc_id}")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json["success"])

    def test_hyphenated_continuation_merge(self):
        # 1. Test _join_wrapped_lines
        lines_word_break = ["Esta lei é constitu-", "cional para todos."]
        self.assertEqual(webapp._join_wrapped_lines(lines_word_break), "Esta lei é constitucional para todos.")

        lines_compound = ["Este decreto-", "lei regulamenta a matéria."]
        self.assertEqual(webapp._join_wrapped_lines(lines_compound), "Este decreto-lei regulamenta a matéria.")

        lines_enclitic = ["Dá-", "se provimento ao recurso."]
        self.assertEqual(webapp._join_wrapped_lines(lines_enclitic), "Dá-se provimento ao recurso.")

        # 2. Test _merge_spurious_continuation_breaks
        content_word_break = "Esta lei é constitu-\n\ncional para todos."
        self.assertIn("Esta lei é constitucional para todos.", webapp._merge_spurious_continuation_breaks(content_word_break))

        content_compound = "Este decreto-\n\nlei regulamenta a matéria."
        self.assertIn("Este decreto-lei regulamenta a matéria.", webapp._merge_spurious_continuation_breaks(content_compound))

        content_enclitic = "Dá-\n\nse provimento ao recurso."
        self.assertIn("Dá-se provimento ao recurso.", webapp._merge_spurious_continuation_breaks(content_enclitic))

    def test_pdf_converter_column_layout_detection(self):
        from markitdown.converters._pdf_converter import extract_text_with_layout_and_columns

        # Define Mock objects inside the test method
        class MockWord:
            def __init__(self, text, x0, x1, top, bottom):
                self.dict = {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom}
            def __getitem__(self, key):
                return self.dict[key]

        class MockPage:
            def __init__(self, width=612, height=792, words=None, text_left="", text_right="", text_all=""):
                self.width = width
                self.height = height
                self.words_list = words or []
                self.text_left = text_left
                self.text_right = text_right
                self.text_all = text_all

            def crop(self, box):
                x0, top, x1, bottom = box
                if x1 < self.width * 0.6:
                    return MockPage(width=self.width, height=self.height, text_all=self.text_left)
                elif x0 > self.width * 0.4:
                    return MockPage(width=self.width, height=self.height, text_all=self.text_right)
                return self

            def extract_words(self):
                return self.words_list

            def extract_text(self):
                return self.text_all

        # Case 1: Two Columns with a clear gutter
        words = [
            MockWord("Esquerda", 50, 100, 100, 115),
            MockWord("Direita", 350, 400, 100, 115)
        ]
        two_col_page = MockPage(
            width=612,
            height=792,
            words=words,
            text_left="Texto da esquerda",
            text_right="Texto da direita"
        )
        extracted = extract_text_with_layout_and_columns(two_col_page)
        self.assertEqual(extracted, "Texto da esquerda\n\nTexto da direita")

        # Case 2: Single Column
        single_words = [
            MockWord("Meio", 280, 320, 100, 115)
        ]
        single_page = MockPage(
            width=612,
            height=792,
            words=single_words,
            text_all="Texto de coluna única"
        )
        extracted_single = extract_text_with_layout_and_columns(single_page)
        self.assertEqual(extracted_single, "Texto de coluna única")

    def test_html_sanitization_lxml_nested_repaired(self):
        # Create a malformed HTML that BS4 + lxml should repair without truncating at early body
        malformed_html = (
            "<html><body>"
            "<h1>Título</h1>"
            "<div>"
            "<p>Texto dentro do div"
            "</body></html>"
            "<p>Texto após o fechamento precoce do body</p>"
        )
        
        response = self.post_file(malformed_html.encode("utf-8"), "documento.html")
        self.assertEqual(response.status_code, 200)
        content = response.json["content"]
        # The content after premature </body> must be fully preserved
        self.assertIn("Texto após o fechamento precoce do body", content)

    @unittest.mock.patch("requests.get")
    def test_dictionary_endpoint_success(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.content = b'[{"word":"teste","xml":"<entry id=\\"teste\\"><form><orth>Teste</orth></form><sense><gramGrp>m.</gramGrp><def>Ato ou efeito de testar.\\nSubmiss\\u00e3o a exame.</def></sense><etym orig=\\"Lat\\">(Lat. _testu_)</etym></entry>"}]'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Set session as logged_in to bypass auth
        with self.client.session_transaction() as sess:
            sess["logged_in"] = True

        response = self.client.get("/api/dictionary?word=teste")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["word"], "teste")
        self.assertEqual(len(response.json["definitions"]), 1)
        
        definition = response.json["definitions"][0]
        self.assertEqual(definition["orth"], "Teste")
        self.assertEqual(definition["gram"], "substantivo masculino")
        self.assertIn("Ato ou efeito de testar", definition["definitions"])
        self.assertEqual(definition["etym"], "(Lat. *testu*)")


if __name__ == "__main__":
    unittest.main()
