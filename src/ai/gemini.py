import os


class ArchipelAI:
    """
    Intégration de Gemini pour fournir des conseils réseau/sécurité.
    """
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.is_active = self.api_key is not None
        self.model = None

        if self.is_active:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
                print("[IA] Assistant Gemini activé ⚠")
            except ImportError:
                print("[IA] Module google-generativeai non installé. Assistant désactivé.")
                self.is_active = False
        else:
            print("[IA] Assistant Gemini désactivé (GEMINI_API_KEY non définie).")

    def ask(self, query: str, context: str = "") -> str:
        if not self.is_active or not self.model:
            return "Mode offline strict — Assistant IA non disponible."
        try:
            prompt = (
                "Tu es l'assistant IA intégré au protocole Archipel (réseau P2P chiffré local).\n"
                f"Contexte réseau actuel : {context}\n\n"
                f"Utilisateur: {query}"
            )
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as exc:
            return f"❌ Erreur IA: {exc}"
