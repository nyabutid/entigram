import http.server
import json
import os
from pathlib import Path
from entigram.federated_router import FederatedRouter

class EntigramGraphQLHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/graphql":
            self.send_error(404, "Not Found")
            return

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            request_data = json.loads(post_data)
            query = request_data.get("query")
            if not query:
                self.send_error(400, "Missing 'query' in request body")
                return

            print(f"🌐 [ENTIGRAM HUB] Executing Federated Query...")
            
            # Initialize router for the current working directory
            # In a real deployment, this would be configured via the CLI
            project_dir = os.environ.get("ENTIGRAM_PROJECT_DIR", ".")
            router = FederatedRouter(project_dir)
            results = router.execute(query)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {"data": results}
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def run_server(port=8080, project_dir="."):
    os.environ["ENTIGRAM_PROJECT_DIR"] = project_dir
    server_address = ('', port)
    httpd = http.server.HTTPServer(server_address, EntigramGraphQLHandler)
    print(f"🚀 Entigram Federated Hub listening on http://localhost:{port}/graphql")
    print(f"📂 Serving project: {Path(project_dir).absolute()}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
