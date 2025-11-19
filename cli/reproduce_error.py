
import requests
import sys
import json

def check_graph():
    url = "http://localhost:8080/graphql"
    query = """
    {
        files: queryFile {
            id
            path
            functionsCount
            classesCount
            importsCount
            containsFunction {
                id
                name
                file
                line
                column
                signature
                callsFunction {
                    id
                    name
                    file
                }
            }
            containsClass {
                id
                name
                file
                line
                column
                methods
                containsMethod {
                    id
                    name
                    file
                    line
                    signature
                }
                inheritsClass {
                    id
                    name
                    file
                }
            }
            containsImport {
                id
                module
                file
                line
            }
        }
    }
    """
    
    try:
        response = requests.post(url, json={"query": query})
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            print("GraphQL Errors found:")
            print(json.dumps(result["errors"], indent=2))
            return False
            
        files = result.get("data", {}).get("files", [])
        print(f"Successfully fetched {len(files)} files with full details.")
        return True
        
    except Exception as e:
        print(f"Request failed: {e}")
        return False

if __name__ == "__main__":
    success = check_graph()
    sys.exit(0 if success else 1)
