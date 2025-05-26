import json
import logging
import os
from typing import Dict, Set, Any

from dotenv import load_dotenv
from litellm import acompletion
from litellm.exceptions import ContextWindowExceededError, APIConnectionError

from core.config import get_settings
from core.models.auth import AuthContext
from core.tools.tools import (
    document_analyzer,
    execute_code,
    knowledge_graph_query,
    list_documents,
    list_graphs,
    retrieve_chunks,
    retrieve_document,
    save_to_memory,
)
from core.utils.agent_helpers import crop_images_in_display_objects, extract_display_object

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

class MorphikAgent:
    """
    Morphik agent for orchestrating tools via LiteLLM function calling.
    """

    def __init__(
        self,
        document_service,
        model: str = None,
    ):
        self.document_service = document_service
        # Load settings
        self.settings = get_settings()
        self.model = model or self.settings.AGENT_MODEL

        # Session‐wide default graph (e.g. "pyRAG")
        self.default_graph = os.getenv("MORPHIK_DEFAULT_GRAPH")
        
        # Conversation history for context
        self.conversation_history = []
        # Define which tools we actually have implemented
        self.implemented_tools: Set[str] = {
            "retrieve_chunks",
            "retrieve_document",
            "document_analyzer",
            "execute_code",
            "knowledge_graph_query",
            "list_graphs",
            "save_to_memory",
            "list_documents",
        }
        # Load tool definitions (function schemas)
        desc_path = os.path.join(os.path.dirname(__file__), "tools", "descriptions.json")
        
        try:
            with open(desc_path, "r") as f:
                all_tools_json = json.load(f)
        except FileNotFoundError:
            logger.error(f"Tool descriptions file not found at {desc_path}")
            all_tools_json = []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in tool descriptions: {e}")
            all_tools_json = []
        # Filter tools to only include implemented ones
        self.tools_json = []
        skipped_tools = []
        
        for tool in all_tools_json:
            tool_name = tool.get("name", "")
            if tool_name in self.implemented_tools:
                self.tools_json.append(tool)
            else:
                skipped_tools.append(tool_name)
        
        if skipped_tools:
            logger.warning(
                f"Skipping {len(skipped_tools)} unimplemented tools from descriptions.json: {', '.join(skipped_tools)}"
            )
        # Build tool definitions for LLM
        self.tool_definitions = []
        for tool in self.tools_json:
            self.tool_definitions.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            })
        logger.info(f"Loaded {len(self.tool_definitions)} tool definitions for LLM")
        # Enhanced system prompt with clearer instructions
        tool_descriptions = [f"- {tool['name']}: {tool['description']}" for tool in self.tools_json]
         
        self.system_prompt = f"""
You are Dante, a research assistant. 
You should use tools to retrieve more context about the user query.
 
WORKFLOW:
1. Detect main entities or keywords in the user request.
2. Call knowledge_graph_query with query_type="list_entities" and those keywords.
3. For each entity returned, call knowledge_graph_query with query_type="entity" or "subgraph" to obtain document_ids.
4. Call retrieve_chunks with the collected document_ids to gather text **before** responding. Only skip tools when the user asks about you or prior conversation, in which case reply from memory.
 
TOOL GUIDELINES:
- Use only the tools listed below. Do not call undefined functions.
- Provide integers for numeric parameters and JSON arrays for lists. Never pass "null" or "None" strings.
- list_documents can show available documents if needed.
 
 Available tools:
 {chr(10).join(tool_descriptions)}
 
After gathering information with tools, ALWAYS provide a final response to the user in the form of a JSON array of display objects. For example:
```json
[
  {{
    "type": "text",
    "content": "Your complete answer after referencing sources as needed.",
    "source": "source-id of the referred document or agent-response",
  }}
]
Ensure the answer is user-friendly and cites relevant sources by using the "source" field for each part of the answer (use the source_id for information taken from documents, or "agent-response" for your own explanatory content). 
Use context from the conversation and any stored memory in your answer when applicable. 
Current default graph: {self.default_graph or "None"}""".strip()
 
    def _clean_tool_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Clean tool arguments from LLM to handle common issues."""
        cleaned = {}
         
        for key, value in args.items():
            # Handle string "null", "None", empty strings
            if isinstance(value, str):
                if value.lower() in ["null", "none", ""]:
                    # Skip optional parameters that are null
                    continue
                # Try to parse numbers
                if key in ["k", "skip", "limit", "max_depth"]:
                    try:
                        cleaned[key] = int(value)
                        continue
                    except ValueError:
                        pass
                 # Try to parse floats
                if key in ["min_relevance"]:
                     try:
                        cleaned[key] = float(value)
                        continue
                     except ValueError:
                        pass
            
            # Keep the value as-is if no special handling needed
            cleaned[key] = value
            
        return cleaned
        
    def _is_personal_question(self, query: str) -> bool:
        """Return True if the query is asking about the agent or past conversation."""
        query_lower = query.lower()
        
        # Personal questions that don't need tools
        personal_patterns = [
            "who are you",
            "what are you",
            "what can you do",
            "how do you work",
            "your capabilities",
            "your functions",
            "you said",
            "you told me",
            "i told you",
            "did i tell you",
            "you mentioned",
            "we discussed",
            "we talked",
            "we spoke",
            "did we discuss",
            "my previous question",
            "previous conversation",
            "earlier you said",
            "remember when",
        ]
        
        # Check if it's a personal question
        for pattern in personal_patterns:
            if pattern in query_lower:
                                return True

        return False

    def _requires_tool_usage(self, query: str) -> bool:
        """Determine if a query requires tool usage."""
        query_lower = query.lower()

        if self._is_personal_question(query):
            return False
        
        # Data retrieval indicators that REQUIRE tools
        data_indicators = [
            "what is", "tell me about", "summarize", "describe",
            "explain", "details", "information about", "from my knowledge",
            "in the knowledge base", "search for", "find", "retrieve",
            "from my database", "list", "show me", "provide", "give me"
        ]
        
        # Check for data retrieval patterns
        for indicator in data_indicators:
            if indicator in query_lower:
                return True
        
        # If query mentions specific entities or concepts, likely needs tools
        if len(query.split()) > 2 and "?" in query:
            return True
                
        return False
    
    def _personal_response(self) -> Dict[str, Any]:
        """Return a standard response describing the agent."""
        text = (
            "I'm Dante, a research assistant designed to help explore and "
            "analyze your knowledge base using various tools."
        )
        return {
            "response": text,
            "tool_history": [],
            "display_objects": [
                {
                    "type": "text",
                    "content": text,
                    "source": "agent-response",
                }
            ],
            "sources": [],
        }

    async def _execute_tool(self, name: str, args: dict, auth: AuthContext, source_map: dict):
        """Dispatch tool calls, injecting document_service and auth."""
        
        # Clean arguments first
        args = self._clean_tool_args(args)

        # Some models may prefix tool names with roles like "system:" or "assistant:".
        # Strip any such prefixes to match the actual implemented tool names.
        if ":" in name:
            name = name.split(":", 1)[-1].strip()
        
        logger.info(f"Executing tool: {name} with cleaned args: {args}")
        
        # Add safety check
        if name not in self.implemented_tools:
            logger.error(f"Tool '{name}' is not implemented. Available tools: {', '.join(sorted(self.implemented_tools))}")
            return f"Error: Tool '{name}' is not available. Please use one of: {', '.join(sorted(self.implemented_tools))}"
        
        try:
            match name:

                case "retrieve_chunks":
                    # Enhanced retrieve_chunks with graph integration
                    query = args.get("query", "")
                    
                    combined_content = []
                    combined_sources = {}

                    # First try knowledge graph to discover related documents
                    if self.default_graph:
                        try:
                            # Search for entities in the graph
                            kg_args = {
                                "query_type": "list_entities",
                                "start_nodes": [query],
                                "graph_name": self.default_graph,
                            }
                            kg_result = await knowledge_graph_query(
                                document_service=self.document_service,
                                auth=auth,
                                **kg_args,
                            )
                            
                            # Parse graph results
                            kg_data = json.loads(kg_result)
                            if kg_data and isinstance(kg_data, list) and len(kg_data) > 0:
                                # Found relevant entities in graph
                                logger.info(f"Found {len(kg_data)} entities in knowledge graph")
                                
                                # Get detailed information for top entities
                                doc_ids: set[str] = set()
                                for entity in kg_data[:3]:
                                    try:
                                        detail_str = await knowledge_graph_query(
                                            document_service=self.document_service,
                                            auth=auth,
                                            query_type="entity",
                                            start_nodes=[entity["id"]],
                                            graph_name=self.default_graph
                                        )
                                        detail = json.loads(detail_str)
                                        doc_ids.update(detail.get("document_ids", []))
                                    except Exception as e:  # pragma: no cover - best effort
                                        logger.warning(f"Failed to get entity details: {e}")
                                
                                if doc_ids:
                                    graph_filters = args.get("filters", {}) or {}
                                    if isinstance(graph_filters, str):
                                        try:
                                            graph_filters = json.loads(graph_filters)
                                        except json.JSONDecodeError:
                                            graph_filters = {}

                                    existing = graph_filters.get("external_id")
                                    if existing:
                                        if isinstance(existing, list):
                                            graph_filters["external_id"] = list(set(existing) | doc_ids)
                                        else:
                                            graph_filters["external_id"] = list(set([existing]) | doc_ids)
                                    else:
                                        graph_filters["external_id"] = list(doc_ids)

                                    graph_args = {**args, "filters": graph_filters}


                                    try:
                                        graph_content, graph_sources = await retrieve_chunks(
                                            document_service=self.document_service,
                                            auth=auth,
                                            **graph_args,
                                        )
                                        combined_content.extend(graph_content)
                                        combined_sources.update(graph_sources)
                                    except Exception as e:  # pragma: no cover
                                        logger.warning(f"Failed to retrieve graph chunks: {e}")
                        except Exception as e:  # pragma: no cover
                            logger.warning(f"Knowledge graph query failed: {e}, falling back to vector search")
                    
                    # Always perform standard vector search
                    try:
                        vec_content, vec_sources = await retrieve_chunks(
                            document_service=self.document_service,
                            auth=auth,
                            **args
                        )
                        combined_content.extend(vec_content)
                        combined_sources.update(vec_sources)
                        source_map.update(combined_sources)
                        return json.dumps(combined_content, ensure_ascii=False)
                    except Exception as e:  # pragma: no cover
                        logger.error(f"Vector search failed: {e}")
                        if not combined_content:
                            return json.dumps([
                                {"type": "text", "text": f"No chunks found for query: {query}"}
                            ])
                        source_map.update(combined_sources)
                        return json.dumps(combined_content, ensure_ascii=False)
                case "retrieve_document":
                    result = await retrieve_document(
                        document_service=self.document_service,
                        auth=auth,
                        **args
                    )
                    if isinstance(result, str) and not result.startswith("Document") and not result.startswith("Error"):
                        doc_id = args.get("document_id", "unknown")
                        source_id = f"doc{doc_id}-full"
                        source_map[source_id] = {
                            "document_id": doc_id,
                            "document_name": f"Full Document {doc_id}",
                            "chunk_number": "full",
                        }
                    return result
                    
                case "document_analyzer":
                    # Check if document_id looks like a concept name instead of ID
                    doc_id = args.get("document_id", "")
                    if doc_id.lower() in ["morphik", "morphism", "document_manik"]:
                        return "Error: document_analyzer requires an actual document ID. Use list_documents first to find document IDs."
                    
                    result = await document_analyzer(
                        document_service=self.document_service,
                        auth=auth,
                        **args
                    )
                    if args.get("document_id"):
                        doc_id = args.get("document_id")
                        analysis_type = args.get("analysis_type", "full")
                        source_id = f"doc{doc_id}-{analysis_type}"
                        source_map[source_id] = {
                            "document_id": doc_id,
                            "document_name": f"Document {doc_id} ({analysis_type})",
                            "analysis_type": analysis_type,
                        }
                    return result
                    
                case "execute_code":
                    res = await execute_code(**args)
                    return json.dumps(res)
                    
                case "knowledge_graph_query":
                    if not args.get("graph_name") and self.default_graph:
                        args["graph_name"] = self.default_graph
                    return await knowledge_graph_query(
                        document_service=self.document_service,
                        auth=auth,
                        **args
                    )
                    
                case "list_graphs":
                    return await list_graphs(
                        document_service=self.document_service,
                        auth=auth,
                        **args
                    )
                    
                case "save_to_memory":
                    return await save_to_memory(
                        document_service=self.document_service,
                        auth=auth,
                        **args
                    )
                    
                case "list_documents":
                    return await list_documents(
                        document_service=self.document_service,
                        auth=auth,
                        **args
                    )
                    
                case _:
                    logger.error(f"Unhandled tool in match statement: {name}")
                    return f"Error: Tool '{name}' is defined but not implemented"
                    
        except Exception as e:
            logger.error(f"Error executing tool {name}: {str(e)}")
            return f"Error executing {name}: {str(e)}"

    async def run(self, query: str, auth: AuthContext) -> str:
        """Run the agent and return the final answer."""
        
        # Handle graph switching
        import re
        m = re.search(r"use\s+knowledge\s+base\s*[:=]\s*([\w\-]+)", query, re.IGNORECASE)
        if m:
            new_graph = m.group(1)
            self.default_graph = new_graph
            query = re.sub(
                r"use\s+knowledge\s+base\s*[:=]\s*[\w\-]+",
                "",
                query,
                flags=re.IGNORECASE,
            ).strip()
            if not query:
                return {
                    "response": f"✅ Knowledge base set to: {new_graph}",
                    "display_objects": [
                        {
                            "type": "text",
                            "content": f"✅ Knowledge base set to: {new_graph}",
                            "source": "agent-response"
                        }
                    ],
                    "sources": []
                }
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": query})
        
        # Determine if this is a personal question and if tools are needed
        is_personal = self._is_personal_question(query)
        requires_tools = self._requires_tool_usage(query)
        logger.info(f"Query requires tools: {requires_tools}")

        if is_personal and not requires_tools:
            response = self._personal_response()
            self.conversation_history.append({"role": "assistant", "content": response["response"]})
            return response
        
        # Per-run state
        source_map: dict = {}
        
        # Build messages with recent history for context
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Include last 5 exchanges for context
        history_window = 10  # 5 user + 5 assistant messages
        if len(self.conversation_history) > history_window:
            messages.extend(self.conversation_history[-history_window:])
        else:
            messages.extend(self.conversation_history)
        
        tool_history = []
        
        # Get model configuration
        settings = get_settings()
        if self.model not in settings.REGISTERED_MODELS:
            raise ValueError(f"Model '{self.model}' not found in registered_models configuration")
        
        model_config = settings.REGISTERED_MODELS[self.model]
        model_name = model_config.get("model_name")
        
        # Prepare model parameters
        model_params = {
            "model": model_name,
            "messages": messages,
            "tools": self.tool_definitions,
            "tool_choice": "required" if requires_tools else "auto",  # Force tool use for data queries
            "temperature": 0.7,
            "max_tokens": 4000,
        }
        
        # Add other parameters from model config
        for key, value in model_config.items():
            if key not in ["model_name", "temperature", "max_tokens"]:
                model_params[key] = value
        
        # Limit iterations
        max_iterations = 10
        iteration = 0
        made_tool_call = False
        consecutive_errors = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Sending completion request (iteration {iteration})")
            
            try:
                resp = await acompletion(**model_params)
            except ContextWindowExceededError as e:
                logger.error("Context window exceeded")
                self.conversation_history = self.conversation_history[-6:]
                raise e
            except APIConnectionError as e:
                logger.error(f"API connection error: {e}")
                if iteration < max_iterations:
                    logger.info("Retrying completion due to connection error")
                    continue
                raise e
            except Exception as e:
                logger.error(f"Error in completion: {e}")
                # If tool_choice="required" fails, retry with "auto"
                if model_params.get("tool_choice") == "required":
                    logger.info("Retrying with tool_choice='auto'")
                    model_params["tool_choice"] = "auto"
                    continue
                raise e
            
            msg = resp.choices[0].message
            
            # Check if this is a tool call
            if getattr(msg, "tool_calls", None):
                made_tool_call = True
                # Handle tool calls
                call = msg.tool_calls[0]
                name = call.function.name
                
                try:
                    args = json.loads(call.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                
                logger.info(f"Tool call detected: {name} with args: {args}")
                
                # Append message with tool calls
                messages.append(msg.to_dict(exclude_none=True))
                
                # Execute tool
                result = await self._execute_tool(name, args, auth, source_map)
                
                # Check if this was an error
                if "Error" in result:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        # Too many errors, force synthesis
                        logger.warning("Too many consecutive errors, forcing synthesis")
                        messages.append({
                            "role": "system",
                            "content": "Multiple tool errors occurred. Please provide the best answer you can based on what you know about the topic."
                        })
                        model_params["tool_choice"] = "none"
                else:
                    consecutive_errors = 0
                
                # Add to tool history
                tool_history.append({
                    "tool_name": name,
                    "tool_args": args,
                    "tool_result": result
                })
                
                # Append tool result
                messages.append({
                    "role": "tool",
                    "name": name,
                    "content": result if isinstance(result, str) else json.dumps(result),
                    "tool_call_id": call.id
                })
                
                # After getting some results, check if we should synthesize
                if made_tool_call and tool_history and iteration >= 2:
                    # Check if we have any meaningful results
                    has_results = any(
                        "Found" in str(h.get("tool_result", "")) and "Found 0" not in str(h.get("tool_result", ""))
                        for h in tool_history
                    )
                    
                    if has_results or iteration >= 5:
                        # Add synthesis instruction
                        messages.append({
                            "role": "system", 
                            "content": "Based on the tool results (even if some were empty), synthesize a comprehensive answer. If you found information, explain it. If not, acknowledge this and provide any general knowledge you have about the topic."
                        })
                        model_params["tool_choice"] = "none"
                        continue
                
                # Continue with more tools if needed
                model_params["tool_choice"] = "auto"
                continue
            
            # No tool calls - check if we should have made one
            if requires_tools and not made_tool_call and iteration == 1:
                logger.warning("Query requires tools but none were called. Forcing tool usage.")
                messages.append({
                    "role": "system",
                    "content": f"You must search for information about '{query}' using the retrieve_chunks tool before answering."
                })
                model_params["tool_choice"] = "required"
                continue
            
            # Process final response
            logger.info("Processing final response")
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": msg.content})
            
            # Parse response as display objects
            display_objects = []
            
            try:
                # Clean and parse JSON response
                content = msg.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                
                parsed = json.loads(content)
                
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "type" in item and "content" in item:
                            obj = extract_display_object(item, source_map)
                            if not obj.get("invalid", False):
                                display_objects.append(obj)
                elif isinstance(parsed, dict) and "type" in parsed and "content" in parsed:
                    obj = extract_display_object(parsed, source_map)
                    if not obj.get("invalid", False):
                        display_objects.append(obj)
                        
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                # Create text display object from content
                if msg.content.strip():
                    display_objects.append({
                        "type": "text",
                        "content": msg.content,
                        "source": "agent-response"
                    })
            
            # Ensure we have at least one display object
            if not display_objects:
                if tool_history:
                    # Better synthesis from tool results
                    content = self._synthesize_tool_results(tool_history, query)
                else:
                    content = "I couldn't find specific information about that in the knowledge base."
                
                display_objects.append({
                    "type": "text",
                    "content": content,
                    "source": "agent-response"
                })
            
            # Create sources
            sources = []
            seen_source_ids = set()
            
            for source_id, source_info in source_map.items():
                if source_id not in seen_source_ids:
                    seen_source_ids.add(source_id)
                    sources.append({
                        "sourceId": source_id,
                        "documentName": source_info.get("document_name", "Unknown"),
                        "documentId": source_info.get("document_id", "unknown"),
                        "content": source_info.get("content", ""),
                    })
            
            # Return result
            display_objects = crop_images_in_display_objects(display_objects)
            return {
                "response": display_objects[0]["content"] if display_objects else "No response generated",
                "tool_history": tool_history,
                "display_objects": display_objects,
                "sources": sources,
            }
        
        # Max iterations reached
        logger.error(f"Max iterations ({max_iterations}) reached")
        
        # Try to provide something useful
        if tool_history:
            content = self._synthesize_tool_results(tool_history, query)
        else:
            content = "I apologize, but I couldn't complete the search properly. Please try rephrasing your question."
        
        return {
            "response": content,
            "tool_history": tool_history,
            "display_objects": [{
                "type": "text",
                "content": content,
                "source": "agent-error"
            }],
            "sources": []
        }

    def _synthesize_tool_results(self, tool_history: list, query: str) -> str:
        """Create a short summary of tool outputs."""
        MAX_SNIPPETS = 3
        snippets = []
        other_messages = []

        # Examine tool outputs
        for hist in tool_history:
            tool_name = hist.get("tool_name", "")
            result_str = hist.get("tool_result", "")
            
            try:
                if tool_name == "retrieve_chunks":
                    result_data = json.loads(result_str)
                    if isinstance(result_data, list):
                        for item in result_data:
                            if (
                                item.get("type") == "text"
                                and "Document:" in item.get("text", "")
                            ):
                                text = item.get("text", "")
                                if "\n\n" in text:
                                    text = text.split("\n\n", 1)[1]
                                text = text.strip().replace("\n", " ")
                                snippet = text[:150]
                                if len(text) > 150:
                                    snippet += "..."
                                snippets.append(snippet)
                                if len(snippets) >= MAX_SNIPPETS:
                                    break
                    if not snippets:
                        other_messages.append(
                            "No relevant chunks were found in the vector search."
                        )

                elif tool_name == "knowledge_graph_query":
                    if "not found" in result_str.lower() or "error" in result_str.lower():
                        other_messages.append(
                            "The knowledge graph query encountered an error."
                        )
                    else:
                        result_data = json.loads(result_str)
                        if "graph_results" in result_data:
                            other_messages.append(
                                "Found information in the knowledge graph."
                            )
                
                elif tool_name == "list_documents":
                    if "error" in result_str.lower():
                        other_messages.append(
                            "Could not list documents due to an error."
                        )
                    else:
                        result_data = json.loads(result_str)
                        doc_count = result_data.get("count", 0)
                        other_messages.append(
                            f"There are {doc_count} documents in the knowledge base."
                        )
                        
            except Exception as e:
                logger.warning(f"Error parsing tool result: {e}")

        if not snippets and not other_messages:
            return (
                f"I searched for information about '{query}' but couldn't find specific details "
                "in the knowledge base."
            )

        bullet_lines = [f"- {s}" for s in snippets[:MAX_SNIPPETS]]
        bullet_lines.extend(f"- {m}" for m in other_messages)

        return "Here is a brief summary of the tool results:\n" + "\n".join(
            bullet_lines
        )
        
    def stream(self, query: str):
        """Streaming stub - not implemented."""
        raise NotImplementedError("Streaming not supported yet; please use run()")
