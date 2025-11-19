"""Dgraph integration for storing and querying code graphs."""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import grpc
import numpy as np
import pydgraph
import requests

from .builder import GraphData
from ..embeddings.service import EmbeddingService
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.models import QwenClient
    from ..config import BadgerConfig

logger = logging.getLogger(__name__)


class DgraphClient:
    """Client for interacting with Dgraph database."""
    
    def __init__(self, endpoint: Optional[str] = None):
        """Initialize Dgraph client.
        
        Args:
            endpoint: Dgraph endpoint URL (defaults to http://localhost:8080 if None)
                     Will be converted to gRPC endpoint (port 9080) and HTTP endpoint (port 8080)
        """
        # Parse endpoint and convert to gRPC and HTTP formats
        if endpoint:
            parsed = urlparse(endpoint)
            hostname = parsed.hostname or 'localhost'
            # Convert HTTP (8080) to gRPC (9080) if needed
            if parsed.port == 8080 or (not parsed.port and '8080' in endpoint):
                grpc_endpoint = f"{hostname}:9080"
                http_endpoint = f"http://{hostname}:8080"
            elif parsed.port:
                grpc_endpoint = f"{hostname}:{parsed.port}"
                http_endpoint = f"http://{hostname}:{parsed.port}"
            else:
                # Assume it's already in hostname:port format
                if ':' in endpoint:
                    grpc_endpoint = endpoint
                    http_endpoint = f"http://{endpoint}"
                else:
                    grpc_endpoint = f"{endpoint}:9080"
                    http_endpoint = f"http://{endpoint}:8080"
        else:
            grpc_endpoint = "localhost:9080"
            http_endpoint = "http://localhost:8080"
        
        self.endpoint = grpc_endpoint
        self.http_endpoint = http_endpoint
        self._graphql_schema_setup = False
        self._embedding_service: Optional[EmbeddingService] = None
        
        # Create client stub (low-level gRPC connection)
        # Configure gRPC options to handle large messages (embeddings can be large)
        # Default max message size is 4MB, we increase to 50MB to handle large batches
        grpc_options = [
            ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50MB
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),  # 50MB
        ]
        
        try:
            self.client_stub = pydgraph.DgraphClientStub(grpc_endpoint, options=grpc_options)
            # Create Dgraph client (high-level interface)
            self.client = pydgraph.DgraphClient(self.client_stub)
        except Exception as e:
            logger.error(f"Failed to initialize Dgraph client: {e}")
            raise
    
    def close(self):
        """Close the client stub and clean up resources."""
        if hasattr(self, 'client_stub'):
            try:
                self.client_stub.close()
            except Exception as e:
                logger.warning(f"Error closing client stub: {e}")
    
    def _generate_uid(self, identifier: str) -> str:
        """Generate deterministic UID from identifier using hash.
        
        Args:
            identifier: Unique identifier string (e.g., file path, function name)
        
        Returns:
            Hexadecimal UID string (without 0x prefix for Dgraph)
        """
        # Use SHA256 for deterministic hashing
        hash_obj = hashlib.sha256(identifier.encode('utf-8'))
        # Convert to hex and take first 16 characters (64 bits)
        # Dgraph UIDs are typically represented as hex strings
        return hash_obj.hexdigest()[:16]
    
    def _get_embedding_service(self) -> EmbeddingService:
        """Get or create the embedding service (lazy loading).
        
        Returns:
            EmbeddingService instance
        """
        if self._embedding_service is None:
            try:
                self._embedding_service = EmbeddingService()
            except Exception as e:
                logger.error(f"Failed to initialize embedding service: {e}")
                raise
        return self._embedding_service
    
    def update_schema(self) -> bool:
        """Force update the GraphQL schema (useful when schema definition changes).
        
        Returns:
            True if successful, False otherwise
        """
        self._graphql_schema_setup = False
        return self.setup_graphql_schema()
    
    def setup_graphql_schema(self) -> bool:
        """Set up GraphQL schema for code graph.
        
        When GraphQL schema is uploaded, Dgraph automatically generates
        the underlying schema, so we don't need separate schema setup.
        
        Returns:
            True if successful, False otherwise
        """
        if self._graphql_schema_setup:
            return True
        
        schema_path = Path(__file__).parent / "graphql_schema.graphql"
        if not schema_path.exists():
            logger.error(f"GraphQL schema file not found: {schema_path}")
            return False
        
        with open(schema_path, 'r') as f:
            graphql_schema = f.read()
        
        # Upload GraphQL schema to Dgraph
        # This auto-generates the underlying database schema
        admin_url = f"{self.http_endpoint}/admin/schema"
        
        headers = {"Content-Type": "application/graphql"}
        
        # Retry logic for schema setup
        max_retries = 5
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                response = requests.post(admin_url, data=graphql_schema, headers=headers, timeout=10)
                
                # Check both status code and response body for errors
                # Dgraph may return 200 with errors in the JSON response
                if response.status_code == 200:
                    try:
                        response_json = response.json()
                        if "errors" in response_json and response_json["errors"]:
                            error_msg = response_json["errors"][0].get("message", "Unknown error")
                            
                            # Check if it's a "not ready" error that we should retry
                            if "not ready" in error_msg.lower() or "retry" in error_msg.lower():
                                if attempt < max_retries - 1:
                                    logger.info(f"Schema setup retry {attempt + 1}/{max_retries}: {error_msg}")
                                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                                    continue
                                else:
                                    logger.error(f"Failed to setup GraphQL schema after {max_retries} retries: {error_msg}")
                                    return False
                            else:
                                logger.error(f"Failed to setup GraphQL schema: {error_msg}")
                                logger.error(f"Full error response: {response.text}")
                                return False
                    except (ValueError, KeyError):
                        # Response is not JSON or doesn't have expected structure
                        # If it's not JSON with errors, assume success
                        pass
                    
                    self._graphql_schema_setup = True
                    logger.info("GraphQL schema setup completed")
                    return True
                else:
                    # Non-200 status code
                    if attempt < max_retries - 1:
                        logger.warning(f"Schema setup got status {response.status_code}, retrying...")
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        logger.error(f"Failed to setup GraphQL schema: HTTP {response.status_code}")
                        return False
                        
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Schema setup request failed (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error(f"Failed to setup GraphQL schema after {max_retries} retries: {e}")
                    return False
        
        return False
    
    def execute_graphql_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query via HTTP.
        
        Args:
            query: GraphQL query string
            variables: Optional variables for the query
        
        Returns:
            Dictionary containing the query result
        """
        try:
            graphql_url = f"{self.http_endpoint}/graphql"
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(graphql_url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if "errors" in result:
                logger.error(f"GraphQL query errors: {result['errors']}")
                return {}
            
            return result.get("data", {})
        except Exception as e:
            logger.error(f"GraphQL query error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {}
    
    def insert_graph(self, graph_data: GraphData) -> bool:
        """Insert graph data into Dgraph.
        
        Args:
            graph_data: Graph data to insert
        
        Returns:
            True if successful, False otherwise
        """
        # Setup GraphQL schema on first insert
        if not self.setup_graphql_schema():
            logger.error("Failed to setup GraphQL schema")
            return False
        
        # Build UID maps for all nodes
        file_uids = {}
        function_uids = {}
        class_uids = {}
        import_uids = {}
        macro_uids = {}
        variable_uids = {}
        typedef_uids = {}
        struct_field_access_uids = {}
        
        # Create all nodes in JSON format
        nodes = []
        
        # Create File nodes
        for file_data in graph_data.files:
            file_path = file_data["path"]
            file_uid = self._generate_uid(file_path)
            file_uids[file_path] = file_uid
            
            node = {
                "uid": f"_:{file_uid}",
                "dgraph.type": "File",
                "File.path": file_path,
                "File.functionsCount": file_data.get("functions_count", 0),
                "File.classesCount": file_data.get("classes_count", 0),
                "File.importsCount": file_data.get("imports_count", 0),
                "File.macrosCount": file_data.get("macros_count", 0),
                "File.variablesCount": file_data.get("variables_count", 0),
                "File.typedefsCount": file_data.get("typedefs_count", 0),
                "File.structFieldAccessesCount": file_data.get("struct_field_accesses_count", 0),
                "File.astNodes": file_data.get("ast_nodes", 0),
            }
            nodes.append(node)
        
        # Create Function nodes
        for func_data in graph_data.functions:
            func_name = func_data["name"]
            func_file = func_data.get("file", "")
            func_line = func_data.get("line", 0)
            
            # Ensure file and line are always present (they should be from builder)
            if not func_file:
                logger.warning(f"Function {func_name} missing file path, skipping")
                continue
            if func_line == 0:
                logger.warning(f"Function {func_name} in {func_file} has invalid line number (0), using 1")
                func_line = 1
            
            func_uid = self._generate_uid(f"{func_name}@{func_file}")
            function_uids[(func_name, func_file)] = func_uid
            
            node = {
                "uid": f"_:{func_uid}",
                "dgraph.type": "Function",
                "Function.name": func_name,
                "Function.file": func_file,
                "Function.line": func_line,
                "Function.column": func_data.get("column", 0),
            }
            
            # Add optional fields
            if "signature" in func_data:
                node["Function.signature"] = func_data["signature"]
            if "parameters" in func_data:
                node["Function.parameters"] = json.dumps(func_data["parameters"]) if isinstance(func_data["parameters"], list) else func_data["parameters"]
            if "return_type" in func_data:
                node["Function.returnType"] = func_data["return_type"]
            if "docstring" in func_data:
                node["Function.docstring"] = func_data["docstring"]
            # Note: belongs_to_class is set later as a UID reference after classes are created
            
            # Generate embedding
            try:
                embedding_service = self._get_embedding_service()
                logger.info(f"Generating embedding for function '{func_name}' with signature={func_data.get('signature')}, docstring={func_data.get('docstring')}")
                embedding = embedding_service.generate_function_embedding(
                    name=func_name,
                    signature=func_data.get("signature"),
                    docstring=func_data.get("docstring")
                )
                if embedding is not None and len(embedding) > 0:
                    # For float32vector type, convert numpy array to list of Python floats
                    # Dgraph expects a plain Python list for float32vector type
                    try:
                        if isinstance(embedding, np.ndarray):
                            # Convert to float32 numpy array first, then to plain Python list
                            embedding_f32 = embedding.astype(np.float32)
                            # Convert to list and ensure all are Python floats (not numpy scalars)
                            embedding_list = [float(x) for x in embedding_f32.tolist()]
                        elif isinstance(embedding, list):
                            # Ensure all values are Python floats (not numpy types)
                            embedding_list = [float(x) for x in embedding]
                        else:
                            embedding_list = [float(x) for x in list(embedding)]
                        
                        # Validate embedding: must be correct dimension and contain valid floats
                        if len(embedding_list) == EmbeddingService.EMBEDDING_DIMENSION and all(
                            isinstance(x, float) and not (np.isnan(x) or np.isinf(x)) 
                            for x in embedding_list
                        ):
                            node["Function.embedding"] = embedding_list
                            logger.info(f"Successfully generated embedding for function '{func_name}' (dimension: {len(embedding_list)})")
                        else:
                            logger.warning(f"Invalid embedding for function '{func_name}': dimension={len(embedding_list)}, expected={EmbeddingService.EMBEDDING_DIMENSION}, contains_nan={any(np.isnan(x) for x in embedding_list) if len(embedding_list) > 0 else False}")
                    except Exception as e:
                        logger.warning(f"Failed to format embedding for function '{func_name}': {e}")
                else:
                    logger.warning(f"Generated empty or None embedding for function '{func_name}'")
            except Exception as e:
                logger.warning(f"Failed to generate embedding for function '{func_name}': {e}", exc_info=True)
                # Continue without embedding rather than failing the entire insertion
            
            nodes.append(node)
        
        # Create Class nodes
        for cls_data in graph_data.classes:
            cls_name = cls_data["name"]
            cls_file = cls_data["file"]
            cls_uid = self._generate_uid(f"{cls_name}@{cls_file}")
            class_uids[(cls_name, cls_file)] = cls_uid
            
            node = {
                "uid": f"_:{cls_uid}",
                "dgraph.type": "Class",
                "Class.name": cls_name,
                "Class.file": cls_file,
                "Class.line": cls_data.get("line", 0),
                "Class.column": cls_data.get("column", 0),
            }
            
            # Add optional fields
            if "methods" in cls_data:
                node["Class.methods"] = cls_data["methods"]
            if "base_classes" in cls_data:
                node["Class.baseClasses"] = cls_data["base_classes"]
            
            # Generate embedding
            try:
                embedding_service = self._get_embedding_service()
                logger.info(f"Generating embedding for class '{cls_name}' with methods={cls_data.get('methods')}")
                embedding = embedding_service.generate_class_embedding(
                    name=cls_name,
                    methods=cls_data.get("methods")
                )
                if embedding is not None and len(embedding) > 0:
                    # For float32vector type, convert numpy array to list of Python floats
                    # Dgraph expects a plain Python list for float32vector type
                    try:
                        if isinstance(embedding, np.ndarray):
                            # Convert to float32 numpy array first, then to plain Python list
                            embedding_f32 = embedding.astype(np.float32)
                            # Convert to list and ensure all are Python floats (not numpy scalars)
                            embedding_list = [float(x) for x in embedding_f32.tolist()]
                        elif isinstance(embedding, list):
                            # Ensure all values are Python floats (not numpy types)
                            embedding_list = [float(x) for x in embedding]
                        else:
                            embedding_list = [float(x) for x in list(embedding)]
                        
                        # Validate embedding: must be correct dimension and contain valid floats
                        if len(embedding_list) == EmbeddingService.EMBEDDING_DIMENSION and all(
                            isinstance(x, float) and not (np.isnan(x) or np.isinf(x)) 
                            for x in embedding_list
                        ):
                            node["Class.embedding"] = embedding_list
                            logger.info(f"Successfully generated embedding for class '{cls_name}' (dimension: {len(embedding_list)})")
                        else:
                            logger.warning(f"Invalid embedding for class '{cls_name}': dimension={len(embedding_list)}, expected={EmbeddingService.EMBEDDING_DIMENSION}, contains_nan={any(np.isnan(x) for x in embedding_list) if len(embedding_list) > 0 else False}")
                    except Exception as e:
                        logger.warning(f"Failed to format embedding for class '{cls_name}': {e}")
                else:
                    logger.warning(f"Generated empty or None embedding for class '{cls_name}'")
            except Exception as e:
                logger.warning(f"Failed to generate embedding for class '{cls_name}': {e}", exc_info=True)
                # Continue without embedding rather than failing the entire insertion
            
            nodes.append(node)
        
        # Create Import nodes
        for imp_data in graph_data.imports:
            imp_file = imp_data["file"]
            imp_module = imp_data.get("module", "")
            imp_line = imp_data.get("line", 0)
            imp_uid = self._generate_uid(f"{imp_module}@{imp_file}@{imp_line}")
            import_uids[(imp_module, imp_file, imp_line)] = imp_uid
            
            node = {
                "uid": f"_:{imp_uid}",
                "dgraph.type": "Import",
                "Import.file": imp_file,
                "Import.line": imp_line,
            }
            
            # Add optional fields
            if "module" in imp_data:
                node["Import.module"] = imp_data["module"]
            if "text" in imp_data:
                node["Import.text"] = imp_data["text"]
            if "imported_items" in imp_data:
                node["Import.importedItems"] = imp_data["imported_items"]
            if "alias" in imp_data:
                node["Import.alias"] = imp_data["alias"]
            
            nodes.append(node)
        
        # Create Macro nodes
        for macro_data in graph_data.macros:
            macro_name = macro_data["name"]
            macro_file = macro_data.get("file", "")
            macro_line = macro_data.get("line", 0)
            
            if not macro_file:
                logger.warning(f"Macro {macro_name} missing file path, skipping")
                continue
            if macro_line == 0:
                logger.warning(f"Macro {macro_name} in {macro_file} has invalid line number (0), using 1")
                macro_line = 1
            
            macro_uid = self._generate_uid(f"{macro_name}@{macro_file}@{macro_line}")
            macro_uids[(macro_name, macro_file, macro_line)] = macro_uid
            
            node = {
                "uid": f"_:{macro_uid}",
                "dgraph.type": "Macro",
                "Macro.name": macro_name,
                "Macro.file": macro_file,
                "Macro.line": macro_line,
                "Macro.column": macro_data.get("column", 0),
            }
            
            if "value" in macro_data:
                node["Macro.value"] = macro_data["value"]
            if "parameters" in macro_data:
                node["Macro.parameters"] = macro_data["parameters"]
            
            nodes.append(node)
        
        # Create Variable nodes
        for var_data in graph_data.variables:
            var_name = var_data["name"]
            var_file = var_data.get("file", "")
            var_line = var_data.get("line", 0)
            
            if not var_file:
                logger.warning(f"Variable {var_name} missing file path, skipping")
                continue
            if var_line == 0:
                logger.warning(f"Variable {var_name} in {var_file} has invalid line number (0), using 1")
                var_line = 1
            
            var_uid = self._generate_uid(f"{var_name}@{var_file}@{var_line}")
            variable_uids[(var_name, var_file, var_line)] = var_uid
            
            node = {
                "uid": f"_:{var_uid}",
                "dgraph.type": "Variable",
                "Variable.name": var_name,
                "Variable.file": var_file,
                "Variable.line": var_line,
                "Variable.column": var_data.get("column", 0),
                "Variable.isGlobal": var_data.get("is_global", False),
            }
            
            if "type" in var_data:
                node["Variable.type"] = var_data["type"]
            if "storage_class" in var_data:
                node["Variable.storageClass"] = var_data["storage_class"]
            
            nodes.append(node)
        
        # Create Typedef nodes
        for tdef_data in graph_data.typedefs:
            tdef_name = tdef_data["name"]
            tdef_file = tdef_data.get("file", "")
            tdef_line = tdef_data.get("line", 0)
            
            if not tdef_file:
                logger.warning(f"Typedef {tdef_name} missing file path, skipping")
                continue
            if tdef_line == 0:
                logger.warning(f"Typedef {tdef_name} in {tdef_file} has invalid line number (0), using 1")
                tdef_line = 1
            
            tdef_uid = self._generate_uid(f"{tdef_name}@{tdef_file}@{tdef_line}")
            typedef_uids[(tdef_name, tdef_file, tdef_line)] = tdef_uid
            
            node = {
                "uid": f"_:{tdef_uid}",
                "dgraph.type": "Typedef",
                "Typedef.name": tdef_name,
                "Typedef.file": tdef_file,
                "Typedef.line": tdef_line,
                "Typedef.column": tdef_data.get("column", 0),
            }
            
            if "underlying_type" in tdef_data:
                node["Typedef.underlyingType"] = tdef_data["underlying_type"]
            
            nodes.append(node)
        
        # Create StructFieldAccess nodes
        for sfa_data in graph_data.struct_field_accesses:
            struct_name = sfa_data["struct_name"]
            field_name = sfa_data["field_name"]
            sfa_file = sfa_data.get("file", "")
            sfa_line = sfa_data.get("line", 0)
            
            if not sfa_file:
                logger.warning(f"StructFieldAccess {struct_name}.{field_name} missing file path, skipping")
                continue
            if sfa_line == 0:
                logger.warning(f"StructFieldAccess {struct_name}.{field_name} in {sfa_file} has invalid line number (0), using 1")
                sfa_line = 1
            
            sfa_uid = self._generate_uid(f"{struct_name}.{field_name}@{sfa_file}@{sfa_line}")
            struct_field_access_uids[(struct_name, field_name, sfa_file, sfa_line)] = sfa_uid
            
            node = {
                "uid": f"_:{sfa_uid}",
                "dgraph.type": "StructFieldAccess",
                "StructFieldAccess.structName": struct_name,
                "StructFieldAccess.fieldName": field_name,
                "StructFieldAccess.file": sfa_file,
                "StructFieldAccess.line": sfa_line,
                "StructFieldAccess.column": sfa_data.get("column", 0),
            }
            
            if "access_type" in sfa_data:
                node["StructFieldAccess.accessType"] = sfa_data["access_type"]
            
            nodes.append(node)
        
        # Add relationships
        relationship_stats = {
            "function_call": {"total": 0, "created": 0, "caller_not_found": 0, "callee_not_found": 0},
            "inheritance": {"total": 0, "created": 0, "derived_not_found": 0, "base_not_found": 0},
            "import": {"total": 0, "created": 0},
        }
        
        for rel in graph_data.relationships:
            rel_type = rel.get("type")
            
            if rel_type == "function_call":
                relationship_stats["function_call"]["total"] += 1
                caller_name = rel.get("caller")
                callee_name = rel.get("callee")
                file_path = rel.get("file")  # This is the caller's file
                
                # Handle module-level calls: map "module" to "<module>"
                if caller_name == "module":
                    caller_name = "<module>"
                
                # Find caller in the caller's file
                caller_uid = None
                if (caller_name, file_path) in function_uids:
                    caller_uid = function_uids[(caller_name, file_path)]
                
                if caller_uid:
                    # Try to find callee function UID (may be in different file)
                    # First try exact match
                    callee_uid = None
                    for (name, path), uid in function_uids.items():
                        if name == callee_name:
                            callee_uid = uid
                            break
                    
                    # If exact match failed and callee_name contains dots (e.g., "obj.method"),
                    # try matching just the last part (method name)
                    if not callee_uid and "." in callee_name:
                        method_name = callee_name.split(".")[-1]
                        for (name, path), uid in function_uids.items():
                            if name == method_name:
                                callee_uid = uid
                                logger.debug(
                                    f"Function call matched using method name fallback: "
                                    f"'{callee_name}' -> '{method_name}' (caller: '{caller_name}' in {file_path})"
                                )
                                break
                    
                    if callee_uid:
                        # Add relationship to caller node (callsFunction)
                        for node in nodes:
                            if node.get("uid") == f"_:{caller_uid}":
                                if "Function.callsFunction" not in node:
                                    node["Function.callsFunction"] = []
                                node["Function.callsFunction"].append({"uid": f"_:{callee_uid}"})
                                relationship_stats["function_call"]["created"] += 1
                                break
                        
                        # Explicitly add inverse relationship (calledByFunction)
                        # Dgraph's @hasInverse may not auto-populate, so we do it explicitly
                        for node in nodes:
                            if node.get("uid") == f"_:{callee_uid}":
                                if "Function.calledByFunction" not in node:
                                    node["Function.calledByFunction"] = []
                                node["Function.calledByFunction"].append({"uid": f"_:{caller_uid}"})
                                break
                    else:
                        relationship_stats["function_call"]["callee_not_found"] += 1
                        logger.debug(
                            f"Function call relationship skipped: callee '{callee_name}' not found "
                            f"(caller: '{caller_name}' in {file_path})"
                        )
                else:
                    relationship_stats["function_call"]["caller_not_found"] += 1
                    logger.debug(
                        f"Function call relationship skipped: caller '{caller_name}' not found in {file_path} "
                        f"(callee: '{callee_name}')"
                    )
            
            elif rel_type == "inheritance":
                derived = rel.get("derived")
                base = rel.get("base")
                file_path = rel.get("file")
                
                if (derived, file_path) in class_uids:
                    derived_uid = class_uids[(derived, file_path)]
                    # Try to find base class UID (may be in different file)
                    base_uid = None
                    for (name, path), uid in class_uids.items():
                        if name == base:
                            base_uid = uid
                            break
                    
                    if base_uid:
                        # Add inheritance relationship (inheritsClass)
                        for node in nodes:
                            if node.get("uid") == f"_:{derived_uid}":
                                if "Class.inheritsClass" not in node:
                                    node["Class.inheritsClass"] = []
                                node["Class.inheritsClass"].append({"uid": f"_:{base_uid}"})
                                break
                        
                        # Explicitly add inverse relationship (inheritedByClass)
                        # Dgraph's @hasInverse may not auto-populate, so we do it explicitly
                        for node in nodes:
                            if node.get("uid") == f"_:{base_uid}":
                                if "Class.inheritedByClass" not in node:
                                    node["Class.inheritedByClass"] = []
                                node["Class.inheritedByClass"].append({"uid": f"_:{derived_uid}"})
                                break
            
            elif rel_type == "import":
                file_path = rel.get("file")
                if file_path in file_uids:
                    file_uid = file_uids[file_path]
                    # Find import node for this file
                    for (module, path, line), imp_uid in import_uids.items():
                        if path == file_path:
                            for node in nodes:
                                if node.get("uid") == f"_:{file_uid}":
                                    if "File.containsImport" not in node:
                                        node["File.containsImport"] = []
                                    node["File.containsImport"].append({"uid": f"_:{imp_uid}"})
                                    break
                            break
            
            elif rel_type == "macro_usage":
                macro_name = rel.get("macro")
                usage_file = rel.get("file")
                
                # Find macro node(s) with this name
                matching_macro_uids = []
                for (name, file_path, line), uid in macro_uids.items():
                    if name == macro_name:
                        matching_macro_uids.append(uid)
                
                # Find file node where macro is used
                if usage_file in file_uids and matching_macro_uids:
                    file_uid = file_uids[usage_file]
                    for macro_uid in matching_macro_uids:
                        # Add usesMacro relationship from File to Macro
                        for node in nodes:
                            if node.get("uid") == f"_:{file_uid}":
                                if "File.usesMacro" not in node:
                                    node["File.usesMacro"] = []
                                node["File.usesMacro"].append({"uid": f"_:{macro_uid}"})
                                break
            
            elif rel_type == "variable_usage":
                var_name = rel.get("variable")
                usage_file = rel.get("file")
                usage_function = rel.get("function")
                
                # Find variable node(s) with this name
                matching_var_uids = []
                for (name, file_path, line), uid in variable_uids.items():
                    if name == var_name:
                        matching_var_uids.append((uid, file_path, line))
                
                # Find function node where variable is used
                if usage_function and usage_file:
                    func_uid = None
                    for (name, file_path), uid in function_uids.items():
                        if name == usage_function and file_path == usage_file:
                            func_uid = uid
                            break
                    
                    if func_uid and matching_var_uids:
                        # Use first matching variable (shadowing handled in builder)
                        var_uid = matching_var_uids[0][0]
                        # Add usesVariable relationship from Function to Variable
                        for node in nodes:
                            if node.get("uid") == f"_:{func_uid}":
                                if "Function.usesVariable" not in node:
                                    node["Function.usesVariable"] = []
                                node["Function.usesVariable"].append({"uid": f"_:{var_uid}"})
                                break
            
            elif rel_type == "typedef_usage":
                typedef_name = rel.get("typedef")
                usage_file = rel.get("file")
                
                # Find typedef node(s) with this name
                matching_typedef_uids = []
                for (name, file_path, line), uid in typedef_uids.items():
                    if name == typedef_name:
                        matching_typedef_uids.append(uid)
                
                # Find file node where typedef is used
                if usage_file in file_uids and matching_typedef_uids:
                    file_uid = file_uids[usage_file]
                    for typedef_uid in matching_typedef_uids:
                        # Add usesTypedef relationship from File to Typedef
                        for node in nodes:
                            if node.get("uid") == f"_:{file_uid}":
                                if "File.usesTypedef" not in node:
                                    node["File.usesTypedef"] = []
                                node["File.usesTypedef"].append({"uid": f"_:{typedef_uid}"})
                                break
        
        # Log relationship statistics
        if relationship_stats["function_call"]["total"] > 0:
            stats = relationship_stats["function_call"]
            logger.info(
                f"Function call relationships: {stats['created']}/{stats['total']} created, "
                f"{stats['caller_not_found']} callers not found, {stats['callee_not_found']} callees not found"
            )
        
        # Add file containment relationships and class-method relationships
        for func_data in graph_data.functions:
            func_file = func_data["file"]
            func_name = func_data["name"]
            if func_file in file_uids and (func_name, func_file) in function_uids:
                file_uid = file_uids[func_file]
                func_uid = function_uids[(func_name, func_file)]
                
                # Add file contains function relationship
                for node in nodes:
                    if node.get("uid") == f"_:{file_uid}":
                        if "File.containsFunction" not in node:
                            node["File.containsFunction"] = []
                        node["File.containsFunction"].append({"uid": f"_:{func_uid}"})
                        break
                
                # Add class contains method relationship if this is a method
                if "belongs_to_class" in func_data:
                    class_name = func_data["belongs_to_class"]
                    # Find the class UID
                    for (cls_n, cls_f), cls_uid in class_uids.items():
                        if cls_n == class_name and cls_f == func_file:
                            # Set function.belongs_to_class UID reference on the function node
                            for node in nodes:
                                if node.get("uid") == f"_:{func_uid}":
                                    node["Function.belongsToClass"] = {"uid": f"_:{cls_uid}"}
                                    break
                            
                            # Add reverse relationship to class node
                            for node in nodes:
                                if node.get("uid") == f"_:{cls_uid}":
                                    if "Class.containsMethod" not in node:
                                        node["Class.containsMethod"] = []
                                    node["Class.containsMethod"].append({"uid": f"_:{func_uid}"})
                                    break
                            break
        
        for cls_data in graph_data.classes:
            cls_file = cls_data["file"]
            cls_name = cls_data["name"]
            if cls_file in file_uids and (cls_name, cls_file) in class_uids:
                file_uid = file_uids[cls_file]
                cls_uid = class_uids[(cls_name, cls_file)]
                
                for node in nodes:
                    if node.get("uid") == f"_:{file_uid}":
                        if "File.containsClass" not in node:
                            node["File.containsClass"] = []
                        node["File.containsClass"].append({"uid": f"_:{cls_uid}"})
                        break
        
        for imp_data in graph_data.imports:
            imp_file = imp_data["file"]
            imp_module = imp_data.get("module", "")
            imp_line = imp_data.get("line", 0)
            if imp_file in file_uids and (imp_module, imp_file, imp_line) in import_uids:
                file_uid = file_uids[imp_file]
                imp_uid = import_uids[(imp_module, imp_file, imp_line)]
                
                for node in nodes:
                    if node.get("uid") == f"_:{file_uid}":
                        if "File.containsImport" not in node:
                            node["File.containsImport"] = []
                        node["File.containsImport"].append({"uid": f"_:{imp_uid}"})
                        break
        
        # Add file containment relationships for macros
        for macro_data in graph_data.macros:
            macro_file = macro_data["file"]
            macro_name = macro_data["name"]
            macro_line = macro_data.get("line", 0)
            if macro_file in file_uids and (macro_name, macro_file, macro_line) in macro_uids:
                file_uid = file_uids[macro_file]
                macro_uid = macro_uids[(macro_name, macro_file, macro_line)]
                
                for node in nodes:
                    if node.get("uid") == f"_:{file_uid}":
                        if "File.containsMacro" not in node:
                            node["File.containsMacro"] = []
                        node["File.containsMacro"].append({"uid": f"_:{macro_uid}"})
                        break
                
                # Set containedInFile on macro node
                for node in nodes:
                    if node.get("uid") == f"_:{macro_uid}":
                        node["Macro.containedInFile"] = {"uid": f"_:{file_uid}"}
                        break
        
        # Add file containment relationships for variables
        for var_data in graph_data.variables:
            var_file = var_data["file"]
            var_name = var_data["name"]
            var_line = var_data.get("line", 0)
            if var_file in file_uids and (var_name, var_file, var_line) in variable_uids:
                file_uid = file_uids[var_file]
                var_uid = variable_uids[(var_name, var_file, var_line)]
                
                for node in nodes:
                    if node.get("uid") == f"_:{file_uid}":
                        if "File.containsVariable" not in node:
                            node["File.containsVariable"] = []
                        node["File.containsVariable"].append({"uid": f"_:{var_uid}"})
                        break
                
                # Set containedInFile on variable node
                for node in nodes:
                    if node.get("uid") == f"_:{var_uid}":
                        node["Variable.containedInFile"] = {"uid": f"_:{file_uid}"}
                        break
        
        # Add file containment relationships for typedefs
        for tdef_data in graph_data.typedefs:
            tdef_file = tdef_data["file"]
            tdef_name = tdef_data["name"]
            tdef_line = tdef_data.get("line", 0)
            if tdef_file in file_uids and (tdef_name, tdef_file, tdef_line) in typedef_uids:
                file_uid = file_uids[tdef_file]
                tdef_uid = typedef_uids[(tdef_name, tdef_file, tdef_line)]
                
                for node in nodes:
                    if node.get("uid") == f"_:{file_uid}":
                        if "File.containsTypedef" not in node:
                            node["File.containsTypedef"] = []
                        node["File.containsTypedef"].append({"uid": f"_:{tdef_uid}"})
                        break
                
                # Set containedInFile on typedef node
                for node in nodes:
                    if node.get("uid") == f"_:{tdef_uid}":
                        node["Typedef.containedInFile"] = {"uid": f"_:{file_uid}"}
                        break
        
        # Add file containment relationships for struct field accesses
        for sfa_data in graph_data.struct_field_accesses:
            sfa_file = sfa_data["file"]
            struct_name = sfa_data["struct_name"]
            field_name = sfa_data["field_name"]
            sfa_line = sfa_data.get("line", 0)
            if sfa_file in file_uids and (struct_name, field_name, sfa_file, sfa_line) in struct_field_access_uids:
                file_uid = file_uids[sfa_file]
                sfa_uid = struct_field_access_uids[(struct_name, field_name, sfa_file, sfa_line)]
                
                for node in nodes:
                    if node.get("uid") == f"_:{file_uid}":
                        if "File.containsStructFieldAccess" not in node:
                            node["File.containsStructFieldAccess"] = []
                        node["File.containsStructFieldAccess"].append({"uid": f"_:{sfa_uid}"})
                        break
                
                # Set containedInFile on struct field access node
                for node in nodes:
                    if node.get("uid") == f"_:{sfa_uid}":
                        node["StructFieldAccess.containedInFile"] = {"uid": f"_:{file_uid}"}
                        break
                
                # Link to Class (struct) if resolved
                if "resolved_struct_name" in sfa_data and "resolved_struct_file" in sfa_data:
                    resolved_name = sfa_data["resolved_struct_name"]
                    resolved_file = sfa_data["resolved_struct_file"]
                    if (resolved_name, resolved_file) in class_uids:
                        struct_uid = class_uids[(resolved_name, resolved_file)]
                        for node in nodes:
                            if node.get("uid") == f"_:{sfa_uid}":
                                node["StructFieldAccess.accessesStruct"] = {"uid": f"_:{struct_uid}"}
                                break
        
        # Keep blank nodes as-is - Dgraph will resolve them within the transaction
        # For files, use upsert to ensure we update existing nodes instead of creating duplicates
        # This is handled by the @upsert directive on file.path in the schema
        
        # Batch insert nodes (1000 per batch)
        # Filter out any nodes with invalid embeddings before sending to Dgraph
        # Also ensure all embedding values are native Python floats (not numpy types)
        # IMPORTANT: For vectors in Dgraph, the list must be a proper Python list
        # and pydgraph's set_obj should preserve it correctly
        valid_nodes = []
        for node in nodes:
            # Check if node has embedding fields and validate them
            if "Function.embedding" in node:
                emb = node["Function.embedding"]
                if isinstance(emb, list) and len(emb) == EmbeddingService.EMBEDDING_DIMENSION:
                    # Ensure all values are native Python floats (not numpy types)
                    # Create a fresh Python list to ensure proper serialization
                    try:
                        embedding_list = list([float(x) for x in emb])
                        node["Function.embedding"] = embedding_list
                        # Debug: log first few values to verify format
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Function embedding format check: type={type(embedding_list)}, first_3={embedding_list[:3] if len(embedding_list) >= 3 else embedding_list}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Removing invalid Function.embedding from node {node.get('Function.name', 'unknown')}: {e}")
                        del node["Function.embedding"]
                else:
                    logger.warning(f"Removing invalid Function.embedding from node {node.get('Function.name', 'unknown')}: not a list or wrong dimension")
                    del node["Function.embedding"]
            if "Class.embedding" in node:
                emb = node["Class.embedding"]
                if isinstance(emb, list) and len(emb) == EmbeddingService.EMBEDDING_DIMENSION:
                    # Ensure all values are native Python floats (not numpy types)
                    # Create a fresh Python list to ensure proper serialization
                    try:
                        embedding_list = list([float(x) for x in emb])
                        node["Class.embedding"] = embedding_list
                        # Debug: log first few values to verify format
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Class embedding format check: type={type(embedding_list)}, first_3={embedding_list[:3] if len(embedding_list) >= 3 else embedding_list}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Removing invalid Class.embedding from node {node.get('Class.name', 'unknown')}: {e}")
                        del node["Class.embedding"]
                else:
                    logger.warning(f"Removing invalid Class.embedding from node {node.get('Class.name', 'unknown')}: not a list or wrong dimension")
                    del node["Class.embedding"]
            valid_nodes.append(node)
        
        batch_size = 1000
        max_retries = 3
        retry_delay = 0.5  # Delay for "not ready" retries
        
        for i in range(0, len(valid_nodes), batch_size):
            batch = valid_nodes[i:i + batch_size]
            
            # Debug: Dump batch to JSON file to inspect vector format
            try:
                debug_file = Path(__file__).parent.parent.parent / "graph.json"
                with open(debug_file, 'w') as f:
                    json.dump(batch, f, indent=2, default=str)
                logger.info(f"Debug: Dumped batch {i//batch_size + 1} to {debug_file} ({len(batch)} nodes)")
            except Exception as e:
                logger.warning(f"Failed to write debug file: {e}")
            
            # Split batch: nodes with embeddings vs without
            # pydgraph's set_obj expands lists, breaking vectors, so we need to handle embeddings separately
            batch_without_embeddings = []
            embeddings_to_update = []  # List of (embedding_type, name, file, embedding_value)
            
            for node in batch:
                node_copy = node.copy()
                
                # Extract and remove embeddings for separate update
                if "Function.embedding" in node_copy:
                    name = node_copy.get("Function.name", "")
                    file = node_copy.get("Function.file", "")
                    embedding = node_copy.pop("Function.embedding")
                    if name and file:
                        embeddings_to_update.append(("function", name, file, embedding))
                if "Class.embedding" in node_copy:
                    name = node_copy.get("Class.name", "")
                    file = node_copy.get("Class.file", "")
                    embedding = node_copy.pop("Class.embedding")
                    if name and file:
                        embeddings_to_update.append(("class", name, file, embedding))
                
                batch_without_embeddings.append(node_copy)
            
            # Insert nodes without embeddings via gRPC
            for attempt in range(max_retries):
                try:
                    txn = self.client.txn()
                    try:
                        mutation = txn.create_mutation(set_obj=batch_without_embeddings)
                        commit_now = (i + batch_size >= len(valid_nodes)) and len(embeddings_to_update) == 0
                        txn.mutate(mutation, commit_now=commit_now)
                        if not commit_now:
                            txn.commit()
                        break  # Success, exit retry loop
                    except pydgraph.AbortedError:
                        # Transaction conflict, retry
                        if attempt < max_retries - 1:
                            time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                            continue
                        else:
                            raise
                    finally:
                        txn.discard()
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a "not ready" error that we should retry
                    if ("not ready" in error_str.lower() or "retry" in error_str.lower()) and attempt < max_retries - 1:
                        logger.info(f"Insert batch {i//batch_size + 1} retry {attempt + 1}/{max_retries}: {e}")
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                        continue
                    elif attempt == max_retries - 1:
                        logger.error(f"Failed to insert batch {i//batch_size + 1}: {e}")
                        return False
                    else:
                        # Other errors, retry with exponential backoff
                        time.sleep(0.1 * (2 ** attempt))
            
            # Update embeddings via GraphQL mutations (which properly handle vectors)
            # We query nodes by their properties (name + file) since blank node UIDs aren't available
            if embeddings_to_update:
                # Group by type for batch updates
                function_embeddings = {}  # {(name, file): embedding}
                class_embeddings = {}  # {(name, file): embedding}
                
                # Group embeddings by type
                for emb_type, name, file, embedding in embeddings_to_update:
                    if emb_type == "function":
                        function_embeddings[(name, file)] = embedding
                    else:  # class
                        class_embeddings[(name, file)] = embedding
                
                # Update function embeddings
                for (name, file), embedding in function_embeddings.items():
                    mutation_query = """
                    mutation($name: String!, $file: String!, $embedding: [Float!]!) {
                        updateFunction(input: {filter: {name: {eq: $name}, file: {eq: $file}}, set: {embedding: $embedding}}) {
                            function {
                                id
                                name
                            }
                        }
                    }
                    """
                    try:
                        result = self.execute_graphql_query(mutation_query, {
                            "name": name,
                            "file": file,
                            "embedding": embedding
                        })
                        if "errors" in result:
                            logger.warning(f"Failed to update function embedding for {name}@{file}: {result.get('errors')}")
                    except Exception as e:
                        logger.warning(f"Failed to update function embedding for {name}@{file}: {e}")
                
                # Update class embeddings
                for (name, file), embedding in class_embeddings.items():
                    mutation_query = """
                    mutation($name: String!, $file: String!, $embedding: [Float!]!) {
                        updateClass(input: {filter: {name: {eq: $name}, file: {eq: $file}}, set: {embedding: $embedding}}) {
                            class {
                                id
                                name
                            }
                        }
                    }
                    """
                    try:
                        result = self.execute_graphql_query(mutation_query, {
                            "name": name,
                            "file": file,
                            "embedding": embedding
                        })
                        if "errors" in result:
                            logger.warning(f"Failed to update class embedding for {name}@{file}: {result.get('errors')}")
                    except Exception as e:
                        logger.warning(f"Failed to update class embedding for {name}@{file}: {e}")
        
        logger.info(f"Successfully inserted {len(nodes)} nodes into Dgraph")
        return True
    
    def query_context(self, query_elements: Dict[str, List[str]]) -> Dict[str, Any]:
        """Query Dgraph for code context using GraphQL.
        
        Args:
            query_elements: Dictionary with keys like 'functions', 'classes', 'variables'
                           containing lists of names to search for
        
        Returns:
            Dictionary containing relevant context from the graph
        """
        if not query_elements:
            return {}
        
        # Build GraphQL query
        query_fields = []
        variables = {}
        
        # Query for functions
        if query_elements.get("functions"):
            func_names = query_elements["functions"]
            for i, func_name in enumerate(func_names):
                var_name = f"funcName{i}"
                variables[var_name] = func_name
                query_fields.append(f"""
            func_{i}: queryFunction(filter: {{name: {{eq: ${var_name}}}}}) {{
                id
                name
                file
                line
                column
                signature
                parameters
                returnType
                docstring
                containedInFile {{
                    path
                }}
                callsFunction {{
                    name
                    file
                    line
                }}
            }}""")
        
        # Query for classes
        if query_elements.get("classes"):
            class_names = query_elements["classes"]
            for i, class_name in enumerate(class_names):
                var_name = f"className{i}"
                variables[var_name] = class_name
                query_fields.append(f"""
            cls_{i}: queryClass(filter: {{name: {{eq: ${var_name}}}}}) {{
                id
                name
                file
                line
                column
                methods
                baseClasses
                containedInFile {{
                    path
                }}
                inheritsClass {{
                    name
                    file
                }}
            }}""")
        
        if not query_fields:
            return {}
        
        query = "query(" + ", ".join([f"${k}: String!" for k in variables.keys()]) + ") {" + "".join(query_fields) + "\n}"
        
        # Execute GraphQL query
        result = self.execute_graphql_query(query, variables)
        
        if not result:
            return {}
        
        # Format response to match existing structure
        formatted = {
            "functions": [],
            "classes": [],
            "files": []
        }
        
        # Extract functions from all func_* query blocks
        for key in result.keys():
            if key.startswith("func_"):
                func_list = result[key] if isinstance(result[key], list) else [result[key]]
                for func in func_list:
                    if not func:
                        continue
                    func_data = {
                        "name": func.get("name", ""),
                        "file": func.get("file", ""),
                        "line": func.get("line", 0),
                        "column": func.get("column", 0),
                    }
                    if "signature" in func:
                        func_data["signature"] = func["signature"]
                    if "parameters" in func:
                        func_data["parameters"] = func["parameters"]
                    if "returnType" in func:
                        func_data["return_type"] = func["returnType"]
                    if "docstring" in func:
                        func_data["docstring"] = func["docstring"]
                    
                    # Get file path from relationship
                    if "containedInFile" in func and func["containedInFile"]:
                        file_data = func["containedInFile"][0] if isinstance(func["containedInFile"], list) else func["containedInFile"]
                        if "path" in file_data:
                            func_data["file"] = file_data["path"]
                    
                    formatted["functions"].append(func_data)
        
        # Extract classes from all cls_* query blocks
        for key in result.keys():
            if key.startswith("cls_"):
                cls_list = result[key] if isinstance(result[key], list) else [result[key]]
                for cls in cls_list:
                    if not cls:
                        continue
                    cls_data = {
                        "name": cls.get("name", ""),
                        "file": cls.get("file", ""),
                        "line": cls.get("line", 0),
                        "column": cls.get("column", 0),
                    }
                    if "methods" in cls:
                        cls_data["methods"] = cls["methods"]
                    if "baseClasses" in cls:
                        cls_data["base_classes"] = cls["baseClasses"]
                    
                    # Get file path from relationship
                    if "containedInFile" in cls and cls["containedInFile"]:
                        file_data = cls["containedInFile"][0] if isinstance(cls["containedInFile"], list) else cls["containedInFile"]
                        if "path" in file_data:
                            cls_data["file"] = file_data["path"]
                    
                    formatted["classes"].append(cls_data)
        
        # Extract unique files
        file_paths = set()
        for func in formatted["functions"]:
            if "file" in func:
                file_paths.add(func["file"])
        for cls in formatted["classes"]:
            if "file" in cls:
                file_paths.add(cls["file"])
        
        formatted["files"] = [{"path": path} for path in file_paths]
        
        return formatted
    
    def update_graph(self, file_path: str, parse_result: Any) -> bool:
        """Update graph with changes from a single file.
        
        Args:
            file_path: Path to the file that was updated
            parse_result: New parse result for the file
        
        Returns:
            True if successful, False otherwise
        """
        from .builder import build_graph
        
        # Build new graph data for this file
        new_graph_data = build_graph([parse_result])
        
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                txn = self.client.txn()
                try:
                    # Query for existing file node using GraphQL
                    file_query = """
                    query($filePath: String!) {
                        file: queryFile(filter: {path: {eq: $filePath}}, first: 1) {
                            id
                            containsFunction {
                                id
                            }
                            containsClass {
                                id
                            }
                            containsImport {
                                id
                            }
                        }
                    }
                    """
                    file_result = self.execute_graphql_query(file_query, {"filePath": file_path})
                    
                    # Collect all UIDs to delete
                    uids_to_delete = []
                    
                    # file_result should have "file" key
                    if isinstance(file_result, dict) and "file" in file_result:
                        file_list = file_result["file"]
                        # file_list should be a list
                        if isinstance(file_list, list) and len(file_list) > 0:
                            file_node = file_list[0]
                            # file_node should be a dict
                            if isinstance(file_node, dict):
                                file_uid = file_node.get("id")
                                if file_uid:
                                    uids_to_delete.append(file_uid)
                                
                                # Collect connected node UIDs
                                if "containsFunction" in file_node and isinstance(file_node["containsFunction"], list):
                                    for func in file_node["containsFunction"]:
                                        if isinstance(func, dict) and "id" in func:
                                            uids_to_delete.append(func["id"])
                                
                                if "containsClass" in file_node and isinstance(file_node["containsClass"], list):
                                    for cls in file_node["containsClass"]:
                                        if isinstance(cls, dict) and "id" in cls:
                                            uids_to_delete.append(cls["id"])
                                
                                if "containsImport" in file_node and isinstance(file_node["containsImport"], list):
                                    for imp in file_node["containsImport"]:
                                        if isinstance(imp, dict) and "id" in imp:
                                            uids_to_delete.append(imp["id"])
                    
                    # Delete existing nodes
                    if uids_to_delete:
                        delete_data = [{"uid": uid} for uid in uids_to_delete]
                        delete_mutation = txn.create_mutation(del_obj=delete_data)
                        txn.mutate(delete_mutation)
                    
                    # Insert new nodes using same logic as insert_graph
                    # Reuse the insert logic but for single file
                    file_uids = {}
                    function_uids = {}
                    class_uids = {}
                    import_uids = {}
                    nodes = []
                    
                    # Create File node (use blank node, upsert will handle uniqueness)
                    if new_graph_data.files:
                        file_data = new_graph_data.files[0]
                        file_uid = self._generate_uid(file_path)
                        file_uids[file_path] = file_uid
                        
                        node = {
                            "uid": f"_:{file_uid}",
                            "dgraph.type": "File",
                            "File.path": file_path,
                            "File.functionsCount": file_data.get("functions_count", 0),
                            "File.classesCount": file_data.get("classes_count", 0),
                            "File.importsCount": file_data.get("imports_count", 0),
                            "File.astNodes": file_data.get("ast_nodes", 0),
                        }
                        nodes.append(node)
                    
                    # Create Function nodes
                    for func_data in new_graph_data.functions:
                        func_name = func_data["name"]
                        func_uid = self._generate_uid(f"{func_name}@{file_path}")
                        function_uids[(func_name, file_path)] = func_uid
                        
                        node = {
                            "uid": f"_:{func_uid}",
                            "dgraph.type": "Function",
                            "Function.name": func_name,
                            "Function.file": file_path,
                            "Function.line": func_data.get("line", 0),
                            "Function.column": func_data.get("column", 0),
                        }
                        
                        if "signature" in func_data:
                            node["Function.signature"] = func_data["signature"]
                        if "parameters" in func_data:
                            node["Function.parameters"] = json.dumps(func_data["parameters"]) if isinstance(func_data["parameters"], list) else func_data["parameters"]
                        if "return_type" in func_data:
                            node["Function.returnType"] = func_data["return_type"]
                        if "docstring" in func_data:
                            node["Function.docstring"] = func_data["docstring"]
                        
                        # Generate embedding
                        try:
                            embedding_service = self._get_embedding_service()
                            embedding = embedding_service.generate_function_embedding(
                                name=func_name,
                                signature=func_data.get("signature"),
                                docstring=func_data.get("docstring")
                            )
                            if embedding is not None and len(embedding) > 0:
                                # For float32vector type, convert numpy array to list of Python floats
                                # Dgraph expects a plain Python list for float32vector type
                                if isinstance(embedding, np.ndarray):
                                    embedding_f32 = embedding.astype(np.float32)
                                    node["Function.embedding"] = [float(x) for x in embedding_f32.tolist()]
                                elif isinstance(embedding, list):
                                    node["Function.embedding"] = [float(x) for x in embedding]
                                else:
                                    node["Function.embedding"] = [float(x) for x in list(embedding)]
                        except Exception as e:
                            logger.error(f"Failed to generate embedding for function '{func_name}': {e}")
                            raise e
                            # Continue without embedding rather than failing the entire update
                        
                        nodes.append(node)
                        
                        # Add relationship to file
                        if file_path in file_uids:
                            for n in nodes:
                                if n.get("uid") == f"_:{file_uids[file_path]}":
                                    if "File.containsFunction" not in n:
                                        n["File.containsFunction"] = []
                                    n["File.containsFunction"].append({"uid": f"_:{func_uid}"})
                                    break
                    
                    # Create Class nodes
                    for cls_data in new_graph_data.classes:
                        cls_name = cls_data["name"]
                        cls_uid = self._generate_uid(f"{cls_name}@{file_path}")
                        class_uids[(cls_name, file_path)] = cls_uid
                        
                        node = {
                            "uid": f"_:{cls_uid}",
                            "dgraph.type": "Class",
                            "Class.name": cls_name,
                            "Class.file": file_path,
                            "Class.line": cls_data.get("line", 0),
                            "Class.column": cls_data.get("column", 0),
                        }
                        
                        if "methods" in cls_data:
                            node["Class.methods"] = cls_data["methods"]
                        if "base_classes" in cls_data:
                            node["Class.baseClasses"] = cls_data["base_classes"]
                        
                        # Generate embedding
                        try:
                            embedding_service = self._get_embedding_service()
                            embedding = embedding_service.generate_class_embedding(
                                name=cls_name,
                                methods=cls_data.get("methods")
                            )
                            if embedding is not None and len(embedding) > 0:
                                # For float32vector type, convert numpy array to list of Python floats
                                # Dgraph expects a plain Python list for float32vector type
                                if isinstance(embedding, np.ndarray):
                                    embedding_f32 = embedding.astype(np.float32)
                                    node["Class.embedding"] = [float(x) for x in embedding_f32.tolist()]
                                elif isinstance(embedding, list):
                                    node["Class.embedding"] = [float(x) for x in embedding]
                                else:
                                    node["Class.embedding"] = [float(x) for x in list(embedding)]
                        except Exception as e:
                            logger.warning(f"Failed to generate embedding for class '{cls_name}': {e}")
                            # Continue without embedding rather than failing the entire update
                        
                        nodes.append(node)
                        
                        # Add relationship to file
                        if file_path in file_uids:
                            for n in nodes:
                                if n.get("uid") == f"_:{file_uids[file_path]}":
                                    if "File.containsClass" not in n:
                                        n["File.containsClass"] = []
                                    n["File.containsClass"].append({"uid": f"_:{cls_uid}"})
                                    break
                    
                    # Create Import nodes
                    for imp_data in new_graph_data.imports:
                        imp_module = imp_data.get("module", "")
                        imp_line = imp_data.get("line", 0)
                        imp_uid = self._generate_uid(f"{imp_module}@{file_path}@{imp_line}")
                        import_uids[(imp_module, file_path, imp_line)] = imp_uid
                        
                        node = {
                            "uid": f"_:{imp_uid}",
                            "dgraph.type": "Import",
                            "Import.file": file_path,
                            "Import.line": imp_line,
                        }
                        
                        if "module" in imp_data:
                            node["Import.module"] = imp_data["module"]
                        if "text" in imp_data:
                            node["Import.text"] = imp_data["text"]
                        if "imported_items" in imp_data:
                            node["Import.importedItems"] = imp_data["imported_items"]
                        if "alias" in imp_data:
                            node["Import.alias"] = imp_data["alias"]
                        
                        nodes.append(node)
                        
                        # Add relationship to file
                        if file_path in file_uids:
                            for n in nodes:
                                if n.get("uid") == f"_:{file_uids[file_path]}":
                                    if "File.containsImport" not in n:
                                        n["File.containsImport"] = []
                                    n["File.containsImport"].append({"uid": f"_:{imp_uid}"})
                                    break
                    
                    # Add function call relationships
                    for rel in new_graph_data.relationships:
                        if rel.get("type") == "function_call":
                            caller_name = rel.get("caller")
                            callee_name = rel.get("callee")
                            
                            # Find caller in the updated file
                            if (caller_name, file_path) in function_uids:
                                caller_uid = function_uids[(caller_name, file_path)]
                                callee_uid = None
                                
                                # First check if callee is in the same file
                                if (callee_name, file_path) in function_uids:
                                    callee_uid = function_uids[(callee_name, file_path)]
                                else:
                                    # Callee might be in a different file - query Dgraph for it using GraphQL
                                    callee_query = """
                                    query($calleeName: String!) {
                                        callee: queryFunction(filter: {name: {eq: $calleeName}}, first: 1) {
                                            id
                                        }
                                    }
                                    """
                                    callee_result = self.execute_graphql_query(callee_query, {"calleeName": callee_name})
                                    
                                    if "callee" in callee_result and len(callee_result["callee"]) > 0:
                                        callee_uid = callee_result["callee"][0].get("id")
                                
                                if callee_uid:
                                    for n in nodes:
                                        if n.get("uid") == f"_:{caller_uid}":
                                            if "Function.callsFunction" not in n:
                                                n["Function.callsFunction"] = []
                                            # If callee is in same file, use blank node; if from Dgraph, use actual UID
                                            if (callee_name, file_path) in function_uids:
                                                # Same file - use blank node format
                                                n["Function.callsFunction"].append({"uid": f"_:{callee_uid}"})
                                            else:
                                                # Cross-file - use actual UID from Dgraph
                                                n["Function.callsFunction"].append({"uid": callee_uid})
                                            break
                    
                    # Split nodes: those with embeddings vs without
                    # pydgraph's set_obj expands lists, breaking vectors
                    nodes_without_embeddings = []
                    embeddings_to_update = []  # List of (embedding_type, name, file, embedding_value)
                    
                    for node in nodes:
                        node_copy = node.copy()
                        
                        # Extract and remove embeddings for separate update
                        if "Function.embedding" in node_copy:
                            name = node_copy.get("Function.name", "")
                            file = node_copy.get("Function.file", "")
                            embedding = node_copy.pop("Function.embedding")
                            if name and file:
                                embeddings_to_update.append(("function", name, file, embedding))
                        if "Class.embedding" in node_copy:
                            name = node_copy.get("Class.name", "")
                            file = node_copy.get("Class.file", "")
                            embedding = node_copy.pop("Class.embedding")
                            if name and file:
                                embeddings_to_update.append(("class", name, file, embedding))
                        
                        nodes_without_embeddings.append(node_copy)
                    
                    # Insert new nodes without embeddings via gRPC
                    if nodes_without_embeddings:
                        mutation = txn.create_mutation(set_obj=nodes_without_embeddings)
                        txn.mutate(mutation)
                    
                    txn.commit()
                    
                    # Update embeddings via GraphQL mutations (which properly handle vectors)
                    if embeddings_to_update:
                        # Group by type
                        function_embeddings = {}  # {(name, file): embedding}
                        class_embeddings = {}  # {(name, file): embedding}
                        
                        for emb_type, name, file, embedding in embeddings_to_update:
                            if emb_type == "function":
                                function_embeddings[(name, file)] = embedding
                            else:  # class
                                class_embeddings[(name, file)] = embedding
                        
                        # Update function embeddings
                        for (name, file), embedding in function_embeddings.items():
                            mutation_query = """
                            mutation($name: String!, $file: String!, $embedding: [Float!]!) {
                                updateFunction(input: {filter: {name: {eq: $name}, file: {eq: $file}}, set: {embedding: $embedding}}) {
                                    function {
                                        id
                                        name
                                    }
                                }
                            }
                            """
                            try:
                                result = self.execute_graphql_query(mutation_query, {
                                    "name": name,
                                    "file": file,
                                    "embedding": embedding
                                })
                                if "errors" in result:
                                    logger.warning(f"Failed to update function embedding for {name}@{file}: {result.get('errors')}")
                            except Exception as e:
                                logger.warning(f"Failed to update function embedding for {name}@{file}: {e}")
                        
                        # Update class embeddings
                        for (name, file), embedding in class_embeddings.items():
                            mutation_query = """
                            mutation($name: String!, $file: String!, $embedding: [Float!]!) {
                                updateClass(input: {filter: {name: {eq: $name}, file: {eq: $file}}, set: {embedding: $embedding}}) {
                                    class {
                                        id
                                        name
                                    }
                                }
                            }
                            """
                            try:
                                result = self.execute_graphql_query(mutation_query, {
                                    "name": name,
                                    "file": file,
                                    "embedding": embedding
                                })
                                if "errors" in result:
                                    logger.warning(f"Failed to update class embedding for {name}@{file}: {result.get('errors')}")
                            except Exception as e:
                                logger.warning(f"Failed to update class embedding for {name}@{file}: {e}")
                    
                    logger.info(f"Successfully updated graph for file: {file_path}")
                    return True
                    
                except pydgraph.AbortedError:
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (2 ** attempt))
                        continue
                    else:
                        raise
                finally:
                    txn.discard()
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to update graph for file {file_path}: {e}")
                    return False
                time.sleep(0.1 * (2 ** attempt))
        
        return False
    
    def vector_search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        search_type: str = "both"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search for similar functions/classes using vector similarity.
        
        Args:
            query_embedding: Query embedding vector (384 dimensions)
            top_k: Number of top results to return per type
            search_type: "functions", "classes", or "both" (default)
        
        Returns:
            Dictionary with keys 'functions' and/or 'classes', each containing
            list of matches with: name, file, signature/methods, vector_distance
        """
        # Handle numpy arrays and lists properly
        if query_embedding is None:
            logger.warning("Query embedding is None")
            return {"functions": [], "classes": []}
        
        # Convert to numpy array first to handle both lists and arrays
        query_vec = np.array(query_embedding, dtype=np.float32)
        
        # Check dimension after conversion
        if len(query_vec) != EmbeddingService.EMBEDDING_DIMENSION:
            logger.warning(f"Invalid query embedding dimension: {len(query_vec)}, expected {EmbeddingService.EMBEDDING_DIMENSION}")
            return {"functions": [], "classes": []}
        
        results = {"functions": [], "classes": []}
        
        # Search functions if requested
        if search_type in ("both", "functions"):
            try:
                # Query all functions with embeddings (limit to reasonable number for MVP)
                # In production, could use pagination or DQL's similar_to() for efficiency
                func_query = """
                query {
                    functions: queryFunction(first: 1000, filter: {has: embedding}) {
                        id
                        name
                        file
                        signature
                        docstring
                        embedding
                    }
                }
                """
                
                func_result = self.execute_graphql_query(func_query)
                
                if "functions" in func_result and func_result["functions"]:
                    func_list = func_result["functions"] if isinstance(func_result["functions"], list) else [func_result["functions"]]
                    
                    # Compute similarity for each function
                    similarities = []
                    for func in func_list:
                        if "embedding" not in func or not func["embedding"]:
                            continue
                        
                        func_embedding = np.array(func["embedding"], dtype=np.float32)
                        
                        # Compute cosine similarity
                        # cosine_similarity = dot(a, b) / (norm(a) * norm(b))
                        dot_product = np.dot(query_vec, func_embedding)
                        norm_query = np.linalg.norm(query_vec)
                        norm_func = np.linalg.norm(func_embedding)
                        
                        if norm_query > 0 and norm_func > 0:
                            similarity = dot_product / (norm_query * norm_func)
                            # Convert to distance (1 - similarity) for consistency with Dgraph's vector_distance
                            distance = 1.0 - similarity
                        else:
                            distance = 1.0  # Maximum distance for zero vectors
                        
                        similarities.append({
                            "func": func,
                            "distance": float(distance)
                        })
                    
                    # Sort by distance (lower is better) and take top-K
                    similarities.sort(key=lambda x: x["distance"])
                    top_similar = similarities[:top_k]
                    
                    # Format results
                    for item in top_similar:
                        func = item["func"]
                        results["functions"].append({
                            "name": func.get("name", ""),
                            "file": func.get("file", ""),
                            "signature": func.get("signature", ""),
                            "docstring": func.get("docstring", ""),
                            "vector_distance": item["distance"]
                        })
                
            except Exception as e:
                logger.error(f"Error in function vector search: {e}")
                results["functions"] = []
        
        # Search classes if requested
        if search_type in ("both", "classes"):
            try:
                # Query all classes with embeddings
                class_query = """
                query {
                    classes: queryClass(first: 1000, filter: {has: embedding}) {
                        id
                        name
                        file
                        methods
                        embedding
                    }
                }
                """
                
                class_result = self.execute_graphql_query(class_query)
                
                if "classes" in class_result and class_result["classes"]:
                    class_list = class_result["classes"] if isinstance(class_result["classes"], list) else [class_result["classes"]]
                    
                    # Compute similarity for each class
                    similarities = []
                    for cls in class_list:
                        if "embedding" not in cls or not cls["embedding"]:
                            continue
                        
                        class_embedding = np.array(cls["embedding"], dtype=np.float32)
                        
                        # Compute cosine similarity
                        dot_product = np.dot(query_vec, class_embedding)
                        norm_query = np.linalg.norm(query_vec)
                        norm_class = np.linalg.norm(class_embedding)
                        
                        if norm_query > 0 and norm_class > 0:
                            similarity = dot_product / (norm_query * norm_class)
                            distance = 1.0 - similarity
                        else:
                            distance = 1.0
                        
                        similarities.append({
                            "cls": cls,
                            "distance": float(distance)
                        })
                    
                    # Sort by distance and take top-K
                    similarities.sort(key=lambda x: x["distance"])
                    top_similar = similarities[:top_k]
                    
                    # Format results
                    for item in top_similar:
                        cls = item["cls"]
                        results["classes"].append({
                            "name": cls.get("name", ""),
                            "file": cls.get("file", ""),
                            "methods": cls.get("methods", []),
                            "vector_distance": item["distance"]
                        })
                
            except Exception as e:
                logger.error(f"Error in class vector search: {e}")
                results["classes"] = []
        
        return results
    
    def query_with_vector_search(
        self,
        user_query: str,
        top_k: int = 5,
        qwen_client: Optional["QwenClient"] = None,
        use_llm_query: bool = True
    ) -> Dict[str, Any]:
        """Complete query pipeline: embedding → vector search → LLM query construction → execute.
        
        Args:
            user_query: Natural language query from user
            top_k: Number of top results to return from vector search
            qwen_client: Optional QwenClient instance for LLM query construction.
                        If None and use_llm_query=True, will skip LLM step
            use_llm_query: If True, use LLM to construct GraphQL query. If False, use simple query
        
        Returns:
            Dictionary containing query results with functions, classes, and relationships
        """
        if not user_query or not user_query.strip():
            logger.warning("Empty user query provided")
            return {"functions": [], "classes": [], "files": []}
        
        try:
            # Step 1: Generate query embedding
            embedding_service = self._get_embedding_service()
            query_embedding = embedding_service.generate_query_embedding(user_query)
            
            # Check if embedding is valid (not all zeros)
            if isinstance(query_embedding, np.ndarray):
                embedding_list = query_embedding.tolist()
            else:
                embedding_list = query_embedding
            
            if all(x == 0.0 for x in embedding_list):
                logger.warning("Query embedding is zero vector, returning empty results")
                return {"functions": [], "classes": [], "files": []}
            
            # Step 2: Vector similarity search
            vector_results = self.vector_search_similar(
                query_embedding=embedding_list,
                top_k=top_k,
                search_type="both"
            )
            
            # If no matches found, return empty results
            if not vector_results.get("functions") and not vector_results.get("classes"):
                logger.info("No similar functions or classes found in vector search")
                return {"functions": [], "classes": [], "files": []}
            
            # Step 3: Construct GraphQL query using LLM (if available)
            if use_llm_query and qwen_client:
                try:
                    graphql_query = qwen_client.construct_graphql_query(
                        matched_elements=vector_results,
                        user_query=user_query
                    )
                    
                    # Extract variables from the query (simple parsing)
                    # For MVP, we'll extract function/class names and create variables
                    # This is a simplified approach - in production, could use proper GraphQL parser
                    variables = {}
                    
                    # Extract function names for variables
                    func_names = [f["name"] for f in vector_results.get("functions", [])]
                    for i, name in enumerate(func_names):
                        var_name = f"funcName{i}"
                        if var_name in graphql_query:
                            variables[var_name] = name
                    
                    # Extract class names for variables
                    class_names = [c["name"] for c in vector_results.get("classes", [])]
                    for i, name in enumerate(class_names):
                        var_name = f"className{i}"
                        if var_name in graphql_query:
                            variables[var_name] = name
                    
                    # Step 4: Execute GraphQL query
                    if graphql_query.strip():
                        result = self.execute_graphql_query(graphql_query, variables if variables else None)
                        
                        # Format result to match expected structure
                        return self._format_query_result(result, vector_results)
                    else:
                        logger.warning("LLM generated empty query, falling back to simple query")
                        use_llm_query = False
                        
                except Exception as e:
                    logger.error(f"Error in LLM query construction: {e}")
                    logger.info("Falling back to simple query construction")
                    use_llm_query = False
            
            # Fallback: Use simple query construction (without LLM)
            if not use_llm_query or not qwen_client:
                query_elements = {
                    "functions": [f["name"] for f in vector_results.get("functions", [])],
                    "classes": [c["name"] for c in vector_results.get("classes", [])]
                }
                return self.query_context(query_elements)
            
        except Exception as e:
            logger.error(f"Error in query_with_vector_search: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"functions": [], "classes": [], "files": []}
    
    def _format_query_result(
        self,
        graphql_result: Dict[str, Any],
        vector_results: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Format GraphQL query result to match expected structure.
        
        Args:
            graphql_result: Raw GraphQL query result
            vector_results: Original vector search results for reference
        
        Returns:
            Formatted result with functions, classes, files
        """
        formatted = {
            "functions": [],
            "classes": [],
            "files": []
        }
        
        # Extract functions from all func_* query blocks
        for key in graphql_result.keys():
            if key.startswith("func_"):
                func_list = graphql_result[key] if isinstance(graphql_result[key], list) else [graphql_result[key]]
                for func in func_list:
                    if not func:
                        continue
                    func_data = {
                        "name": func.get("name", ""),
                        "file": func.get("file", ""),
                        "line": func.get("line", 0),
                        "column": func.get("column", 0),
                    }
                    if "signature" in func:
                        func_data["signature"] = func["signature"]
                    if "parameters" in func:
                        func_data["parameters"] = func["parameters"]
                    if "returnType" in func:
                        func_data["return_type"] = func["returnType"]
                    if "docstring" in func:
                        func_data["docstring"] = func["docstring"]
                    
                    # Get file path from relationship
                    if "containedInFile" in func and func["containedInFile"]:
                        file_data = func["containedInFile"][0] if isinstance(func["containedInFile"], list) else func["containedInFile"]
                        if "path" in file_data:
                            func_data["file"] = file_data["path"]
                    
                    formatted["functions"].append(func_data)
        
        # Extract classes from all cls_* query blocks
        for key in graphql_result.keys():
            if key.startswith("cls_"):
                cls_list = graphql_result[key] if isinstance(graphql_result[key], list) else [graphql_result[key]]
                for cls in cls_list:
                    if not cls:
                        continue
                    cls_data = {
                        "name": cls.get("name", ""),
                        "file": cls.get("file", ""),
                        "line": cls.get("line", 0),
                        "column": cls.get("column", 0),
                    }
                    if "methods" in cls:
                        cls_data["methods"] = cls["methods"]
                    if "baseClasses" in cls:
                        cls_data["base_classes"] = cls["baseClasses"]
                    
                    # Get file path from relationship
                    if "containedInFile" in cls and cls["containedInFile"]:
                        file_data = cls["containedInFile"][0] if isinstance(cls["containedInFile"], list) else cls["containedInFile"]
                        if "path" in file_data:
                            cls_data["file"] = file_data["path"]
                    
                    formatted["classes"].append(cls_data)
        
        # Extract unique files
        file_paths = set()
        for func in formatted["functions"]:
            if "file" in func:
                file_paths.add(func["file"])
        for cls in formatted["classes"]:
            if "file" in cls:
                file_paths.add(cls["file"])
        
        formatted["files"] = [{"path": path} for path in file_paths]
        
        return formatted