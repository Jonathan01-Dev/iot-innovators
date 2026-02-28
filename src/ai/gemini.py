import os

class ArchipelAI:
    """
    Intégration facultative de Gemini pour aider l'utilisateur sur le réseau Archipel.
    Désactivable via le flag --no-ai.
    """
    def __init__(self, disabled: bool = False):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.is_active = (not disabled) and (self.api_key is not None)
        self.model = None
        
        if disabled:
            print("[IA] Assistant Gemini désactivé (flag --no-ai).")
        elif self.is_active:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
                print("[IA] Assistant Gemini activé 🧠")
            except ImportError:
                print("[IA] Module google-generativeai non installé. Assistant désactivé.")
                self.is_active = False
        else:
            print("[IA] Assistant Gemini désactivé (GEMINI_API_KEY non définie).")

    def ask(self, query: str, context: str = "") -> str:
        """Pose une question à Gemini avec du contexte optionnel."""
        if not self.is_active or not self.model:
            return "Mode offline strict — Assistant IA non disponible."
            
        try:
            prompt = f"Tu es l'assistant IA intégré au protocole Archipel (réseau P2P chiffré local).\n"
            if context:
                prompt += f"Contexte réseau actuel : {context}\n"
            prompt += f"\nUtilisateur: {query}"
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"❌ Erreur IA: {e}"
