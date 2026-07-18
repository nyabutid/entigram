import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, patch

import requests

from entigram.cli_runner.cloudflare_ollama_proxy import (
    CloudflareProxyConfig,
    CloudflareProxyError,
    CloudflareModelState,
    CloudflareWorkersAIClient,
    DEFAULT_MODEL_ALIAS,
    aggregate_streaming_chat_completion,
    anthropic_count_tokens_response,
    anthropic_error_event,
    anthropic_model_response,
    anthropic_models_response,
    chat_stream_lines,
    cloudflare_setup_instructions,
    classify_model_capability,
    compact_messages_for_cloudflare,
    compact_text,
    config_from_environment,
    discover_cloudflare_model_profiles,
    extract_completion_content,
    generate_stream_lines,
    is_model_control_command,
    launch_cloudflare_claude,
    make_handler,
    model_control_response,
    model_control_selector,
    model_profile_from_cloudflare_item,
    non_stream_chat_response,
    non_stream_generate_response,
    normalize_messages_for_cloudflare,
    parse_env_file,
    parse_tool_arguments,
    prompt_to_messages,
    ps_response,
    retry_sleep_seconds,
    is_retryable_cloudflare_response,
    request_path,
    serve_proxy,
    sse_event_bytes,
    stringify_message_content,
    tags_response,
)


class TestCloudflareOllamaProxy(unittest.TestCase):
    def test_parse_env_file_handles_quotes_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "# ignored",
                        "export CLOUDFLARE_ACCOUNT_ID='abc123'",
                        'CLOUDFLARE_API_TOKEN="secret"',
                        "CLOUDFLARE_AI_MODEL=@cf/zai-org/glm-5.2",
                    ]
                )
            )

            self.assertEqual(
                parse_env_file(path),
                {
                    "CLOUDFLARE_ACCOUNT_ID": "abc123",
                    "CLOUDFLARE_API_TOKEN": "secret",
                    "CLOUDFLARE_AI_MODEL": "@cf/zai-org/glm-5.2",
                },
            )

    @patch.dict(
        "os.environ",
        {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
            "CLOUDFLARE_AI_MODEL": "@cf/zai-org/glm-5.2",
            "CLOUDFLARE_OLLAMA_MODEL_ALIAS": "legacy-glm-cloudflare",
            "CLOUDFLARE_MODEL_PROFILE": "coding",
            "CLOUDFLARE_DISCOVER_MODELS": "false",
            "CLOUDFLARE_PROXY_TIMEOUT_SECONDS": "301",
            "CLOUDFLARE_PROXY_RETRY_ATTEMPTS": "4",
            "CLOUDFLARE_PROXY_RETRY_SLEEP_SECONDS": "7",
            "CLOUDFLARE_PROXY_COMPACT_PROMPTS": "true",
            "CLOUDFLARE_PROXY_MAX_TOOL_RESULT_CHARS": "120",
        },
        clear=True,
    )
    def test_config_from_environment_uses_cloudflare_values(self):
        config = config_from_environment()

        self.assertEqual(config.account_id, "account-id")
        self.assertEqual(config.api_token, "token")
        self.assertEqual(config.model, "@cf/zai-org/glm-5.2")
        self.assertEqual(config.model_alias, "@cf/zai-org/glm-5.2")
        self.assertEqual(config.legacy_model_alias, "legacy-glm-cloudflare")
        self.assertEqual(config.model_profile, "coding")
        self.assertFalse(config.discover_models)
        self.assertEqual(config.timeout_seconds, 301)
        self.assertEqual(config.retry_attempts, 4)
        self.assertEqual(config.retry_sleep_seconds, 7)
        self.assertTrue(config.compact_prompts)
        self.assertEqual(config.max_tool_result_chars, 120)
        self.assertEqual(
            config.chat_completions_url,
            "https://api.cloudflare.com/client/v4/accounts/account-id/ai/v1/chat/completions",
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_config_from_environment_guides_missing_cloudflare_setup(self):
        with self.assertRaisesRegex(CloudflareProxyError, "etg cloudflare-claude") as ctx:
            config_from_environment()

        self.assertIn("CLOUDFLARE_ACCOUNT_ID=<your-account-id>", str(ctx.exception))
        self.assertIn("etg cloudflare-ollama-proxy --smoke-test", str(ctx.exception))
        self.assertIn(cloudflare_setup_instructions(), str(ctx.exception))

    def test_model_alias_maps_to_cloudflare_model(self):
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
            model_alias=DEFAULT_MODEL_ALIAS,
            legacy_model_alias="glm-cloudflare",
        )

        self.assertEqual(config.resolve_model(DEFAULT_MODEL_ALIAS), "@cf/zai-org/glm-5.2")
        self.assertEqual(config.resolve_model("glm-cloudflare"), "@cf/zai-org/glm-5.2")
        self.assertEqual(config.resolve_model("@cf/zai-org/glm-5.2"), "@cf/zai-org/glm-5.2")
        self.assertEqual(config.display_model("@cf/zai-org/glm-5.2"), DEFAULT_MODEL_ALIAS)
        self.assertEqual(config.display_model("glm-cloudflare"), DEFAULT_MODEL_ALIAS)

    def test_model_profile_detects_code_capable_models(self):
        self.assertEqual(
            classify_model_capability(
                "@cf/moonshotai/kimi-k2.7-code",
                description="Code model with multi-turn tool calling for agentic workloads",
                capabilities=("Function calling", "Reasoning"),
            ),
            "coding",
        )
        self.assertEqual(
            classify_model_capability(
                "@cf/zhipu/glm-4.7-flash",
                description="Optimized for dialogue and instruction following",
            ),
            "conversation",
        )

    def test_model_profile_from_cloudflare_item_uses_ai_model_name(self):
        profile = model_profile_from_cloudflare_item(
            {
                "name": "@cf/moonshotai/kimi-k2.7-code",
                "description": "Code optimized model with function calling",
                "task": "Text Generation",
                "capabilities": [{"name": "Function calling"}, {"name": "Reasoning"}],
            }
        )

        self.assertEqual(profile.model_id, "@cf/moonshotai/kimi-k2.7-code")
        self.assertEqual(profile.alias, "@cf/moonshotai/kimi-k2.7-code")
        self.assertEqual(profile.capability, "coding")

    def test_tags_response_advertises_ai_model_names(self):
        profile = model_profile_from_cloudflare_item(
            {
                "name": "moonshotai/kimi-k3",
                "description": "Conversation model",
            }
        )

        tags = tags_response([profile])

        self.assertEqual(tags["models"][0]["name"], "moonshotai/kimi-k3")
        self.assertEqual(tags["models"][1]["name"], "moonshotai/kimi-k3:latest")

    def test_model_state_auto_selects_coding_model_and_keeps_conversation_switch(self):
        class FakeClient:
            config = CloudflareProxyConfig(account_id="account-id", api_token="token")

            def search_models(self):
                return [
                    {
                        "name": "@cf/zhipu/glm-4.7-flash",
                        "description": "Dialogue and instruction following",
                    },
                    {
                        "name": "@cf/moonshotai/kimi-k2.7-code",
                        "description": "Code model for agentic workloads with function calling",
                    },
                ]

        state = CloudflareModelState(
            CloudflareProxyConfig(account_id="account-id", api_token="token")
        )
        profiles = state.refresh(FakeClient())

        self.assertEqual(state.active_model, "@cf/moonshotai/kimi-k2.7-code")
        self.assertEqual(state.active_alias, "@cf/moonshotai/kimi-k2.7-code")
        self.assertEqual([p.model_id for p in profiles], [
            "@cf/zhipu/glm-4.7-flash",
            "@cf/moonshotai/kimi-k2.7-code",
            "@cf/zai-org/glm-5.2",
        ])

        switched = state.switch("conversation")
        self.assertEqual(switched.model_id, "@cf/zhipu/glm-4.7-flash")
        self.assertEqual(state.active_model, "@cf/zhipu/glm-4.7-flash")

    def test_model_state_resolves_deprecated_alias_as_selector_only(self):
        state = CloudflareModelState(
            CloudflareProxyConfig(
                account_id="account-id",
                api_token="token",
                model="moonshotai/kimi-k3",
                legacy_model_alias="cloudflare-kimi-k3",
            )
        )

        self.assertEqual(state.active_alias, "moonshotai/kimi-k3")
        self.assertEqual(state.resolve_model("cloudflare-kimi-k3"), "moonshotai/kimi-k3")

    def test_model_control_lists_and_switches_models(self):
        class FakeClient:
            config = CloudflareProxyConfig(account_id="account-id", api_token="token")

            def search_models(self):
                return [
                    {"name": "moonshotai/kimi-k3", "description": "Conversation model"},
                    {"name": "@cf/moonshotai/kimi-k2.7-code", "description": "Code optimized"},
                ]

        state = CloudflareModelState(
            CloudflareProxyConfig(account_id="account-id", api_token="token")
        )
        state.refresh(FakeClient())

        listing = model_control_response("cf model list", state)
        self.assertIn("@cf/moonshotai/kimi-k2.7-code", listing)
        self.assertIn("moonshotai/kimi-k3", listing)
        self.assertIn("cf model coding", listing)

        response = model_control_response("cf model moonshotai/kimi-k3", state)
        self.assertIn("Switched Cloudflare model to moonshotai/kimi-k3", response)
        self.assertEqual(state.active_model, "moonshotai/kimi-k3")

    def test_model_control_command_avoids_claude_slash_namespace(self):
        self.assertTrue(is_model_control_command("cf model list"))
        self.assertTrue(is_model_control_command("cf model coding"))
        self.assertFalse(is_model_control_command("/model list"))
        self.assertEqual(model_control_selector("cf model conversation"), "conversation")
        self.assertEqual(model_control_selector("/model list"), "list")

    @patch("entigram.cli_runner.cloudflare_ollama_proxy.requests.get")
    def test_discover_cloudflare_models_calls_model_search_api(self, get):
        get.return_value = SimpleNamespace(
            ok=True,
            json=lambda: {
                "success": True,
                "result": [
                    {
                        "name": "@cf/moonshotai/kimi-k2.7-code",
                        "description": "Code optimized",
                    }
                ],
            },
        )
        config = CloudflareProxyConfig(account_id="account-id", api_token="token")
        profiles = discover_cloudflare_model_profiles(CloudflareWorkersAIClient(config))

        self.assertEqual(profiles[0].model_id, "@cf/moonshotai/kimi-k2.7-code")
        get.assert_called_once()
        _, kwargs = get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")

    def test_compact_text_preserves_head_and_tail(self):
        text = "a" * 100 + "middle" + "z" * 100

        compacted = compact_text(text, 180)

        self.assertLessEqual(len(compacted), 180)
        self.assertTrue(compacted.startswith("a"))
        self.assertTrue(compacted.endswith("z"))
        self.assertIn("compacted an oversized tool result", compacted)

    def test_prompt_compaction_only_truncates_tool_results(self):
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            max_tool_result_chars=180,
        )
        messages = [
            {"role": "user", "content": "x" * 200},
            {"role": "tool", "tool_call_id": "call_1", "content": "y" * 200},
        ]

        compacted = compact_messages_for_cloudflare(messages, config)

        self.assertEqual(compacted[0]["content"], "x" * 200)
        self.assertLessEqual(len(compacted[1]["content"]), 180)
        self.assertIn("compacted an oversized tool result", compacted[1]["content"])

    def test_cloudflare_messages_always_have_string_content(self):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hydrate"}]},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "toolu_1",
                        "type": "function",
                        "function": {"name": "Bash", "arguments": '{"cmd":"hydrate"}'},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "toolu_1",
                "content": [{"type": "text", "text": "large hydrate output"}],
            },
            {"role": "user", "content": {"unexpected": "structured block"}},
        ]

        normalized = normalize_messages_for_cloudflare(messages)

        self.assertEqual(normalized[0]["content"], "hydrate")
        self.assertEqual(normalized[1]["content"], "")
        self.assertEqual(normalized[2]["content"], "large hydrate output")
        self.assertEqual(normalized[3]["content"], '{"unexpected":"structured block"}')
        self.assertTrue(all(isinstance(m["content"], str) for m in normalized))

    def test_stringify_preserves_boundaries_between_text_blocks(self):
        # Failure mode: adjacent text blocks fused with "" joining, corrupting
        # word boundaries in the payload Cloudflare receives.
        content = [
            {"type": "text", "text": "Hello,"},
            {"type": "text", "text": "world."},
        ]
        self.assertEqual(stringify_message_content(content), "Hello,\nworld.")

    def test_stringify_tool_result_with_nested_block_list(self):
        # Failure mode: tool_result content that is itself a list of blocks
        # recursed and fused without separators.
        content = [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": [
                    {"type": "text", "text": "line1"},
                    {"type": "text", "text": "line2"},
                ],
            }
        ]
        self.assertEqual(stringify_message_content(content), "line1\nline2")

    def test_stringify_unknown_block_with_non_serializable_value_degrades(self):
        # Failure mode: json.dumps on an unknown block containing a
        # non-JSON-serializable value raised TypeError -> 500 at the HTTP
        # boundary instead of a normalized payload.
        content = [{"type": "weird", "when": object()}]
        result = stringify_message_content(content)
        self.assertIsInstance(result, str)
        self.assertTrue(result)  # fell back to str(), did not raise

    def test_stringify_handles_none_scalar_and_bytes_content(self):
        # Failure mode: None content must become "" (Cloudflare rejects null
        # content); scalars and bytes must stringify without crashing.
        self.assertEqual(stringify_message_content(None), "")
        self.assertEqual(stringify_message_content(0), "0")
        self.assertEqual(stringify_message_content(True), "True")
        self.assertIsInstance(stringify_message_content(b"raw"), str)

    def test_normalize_drops_empty_blocks_and_keeps_message_shape(self):
        # Failure mode: normalizing a message must not strip sibling keys
        # (tool_calls, tool_call_id) and must leave non-list content intact.
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "text", "text": ""}],
                "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}}],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "plain string"},
        ]
        normalized = normalize_messages_for_cloudflare(messages)
        self.assertEqual(normalized[0]["content"], "")
        self.assertIn("tool_calls", normalized[0])
        self.assertEqual(normalized[1]["content"], "plain string")
        self.assertEqual(normalized[1]["tool_call_id"], "c1")

    def test_prompt_compaction_can_be_disabled(self):
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            compact_prompts=False,
            max_tool_result_chars=10,
        )
        messages = [{"role": "tool", "content": "y" * 200}]

        self.assertEqual(compact_messages_for_cloudflare(messages, config), messages)

    def test_request_path_strips_query_string(self):
        self.assertEqual(request_path("/v1/messages/count_tokens?beta=true"), "/v1/messages/count_tokens")
        self.assertEqual(request_path("/api/tags"), "/api/tags")

    def test_anthropic_model_and_count_token_helpers(self):
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
            model_alias=DEFAULT_MODEL_ALIAS,
        )
        payload = {
            "system": [{"type": "text", "text": "You are concise."}],
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "hello there"}]},
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": "tool output"}],
                },
            ],
            "tools": [{"name": "Bash", "description": "Run a command"}],
        }

        self.assertGreater(anthropic_count_tokens_response(payload)["input_tokens"], 1)
        self.assertEqual(anthropic_model_response(config)["id"], DEFAULT_MODEL_ALIAS)
        self.assertEqual(anthropic_models_response(config)["data"][0]["id"], DEFAULT_MODEL_ALIAS)

    def test_sse_error_event_uses_anthropic_error_shape(self):
        event, payload = anthropic_error_event("capacity temporarily exceeded")
        body = sse_event_bytes(event, payload).decode("utf-8")

        self.assertIn("event: error", body)
        self.assertIn('"type":"api_error"', body)
        self.assertIn("capacity temporarily exceeded", body)

    def test_extract_completion_content_supports_openai_and_cloudflare_envelopes(self):
        openai_payload = {
            "choices": [{"message": {"content": "hello from openai shape"}}],
        }
        cloudflare_payload = {
            "result": {
                "choices": [{"message": {"content": "hello from cloudflare shape"}}],
            }
        }

        self.assertEqual(extract_completion_content(openai_payload), "hello from openai shape")
        self.assertEqual(
            extract_completion_content(cloudflare_payload),
            "hello from cloudflare shape",
        )

    @patch("entigram.cli_runner.cloudflare_ollama_proxy.requests.post")
    def test_cloudflare_client_posts_openai_compatible_chat_payload(self, post):
        post.return_value = SimpleNamespace(
            ok=True,
            json=lambda: {"choices": [{"message": {"content": "ok"}}]},
        )
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
        )

        result = CloudflareWorkersAIClient(config).chat(
            [{"role": "user", "content": "ping"}],
        )

        self.assertEqual(result, "ok")
        post.assert_called_once()
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["model"], "@cf/zai-org/glm-5.2")
        self.assertEqual(kwargs["json"]["messages"], [{"role": "user", "content": "ping"}])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")

    @patch("entigram.cli_runner.cloudflare_ollama_proxy.time.sleep")
    @patch("entigram.cli_runner.cloudflare_ollama_proxy.requests.post")
    def test_cloudflare_client_retries_temporary_capacity_errors(self, post, sleep):
        capacity_error = SimpleNamespace(
            ok=False,
            status_code=429,
            text='{"errors":[{"message":"Capacity temporarily exceeded","code":3040}]}',
        )
        success = SimpleNamespace(
            ok=True,
            json=lambda: {"choices": [{"message": {"content": "ok after retry"}}]},
        )
        post.side_effect = [capacity_error, success]
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
            retry_sleep_seconds=0,
        )

        result = CloudflareWorkersAIClient(config).chat(
            [{"role": "user", "content": "ping"}],
        )

        self.assertEqual(result, "ok after retry")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(0)

    def test_retryable_cloudflare_response_only_retries_capacity_errors(self):
        capacity_error = SimpleNamespace(
            status_code=429,
            text='{"errors":[{"message":"Capacity temporarily exceeded","code":3040}]}',
        )
        quota_error = SimpleNamespace(
            status_code=429,
            text='{"errors":[{"message":"daily free allocation exhausted","code":4006}]}',
        )

        self.assertTrue(is_retryable_cloudflare_response(capacity_error))
        self.assertFalse(is_retryable_cloudflare_response(quota_error))

    def test_retryable_cloudflare_response_retries_gateway_errors(self):
        for status_code in (408, 500, 502, 503, 504, 520, 522, 523, 524):
            with self.subTest(status_code=status_code):
                self.assertTrue(
                    is_retryable_cloudflare_response(
                        SimpleNamespace(status_code=status_code, text="Gateway timeout")
                    )
                )

    def test_retry_sleep_seconds_uses_retry_after_header(self):
        response = SimpleNamespace(headers={"Retry-After": "9"})

        self.assertEqual(retry_sleep_seconds(response, 2), 9)

    @patch("entigram.cli_runner.cloudflare_ollama_proxy.time.sleep")
    @patch("entigram.cli_runner.cloudflare_ollama_proxy.requests.post")
    def test_cloudflare_client_retries_gateway_timeouts(self, post, sleep):
        gateway_timeout = SimpleNamespace(
            ok=False,
            status_code=504,
            text="Gateway Timeout",
            headers={"Retry-After": "0"},
        )
        success = SimpleNamespace(
            ok=True,
            json=lambda: {"choices": [{"message": {"content": "ok after gateway retry"}}]},
        )
        post.side_effect = [gateway_timeout, success]
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
        )

        result = CloudflareWorkersAIClient(config).chat(
            [{"role": "user", "content": "ping"}],
        )

        self.assertEqual(result, "ok after gateway retry")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(0)

    @patch("entigram.cli_runner.cloudflare_ollama_proxy.time.sleep")
    @patch("entigram.cli_runner.cloudflare_ollama_proxy.requests.post")
    def test_cloudflare_client_retries_request_timeouts(self, post, sleep):
        success = SimpleNamespace(
            ok=True,
            json=lambda: {"choices": [{"message": {"content": "ok after request timeout retry"}}]},
        )
        post.side_effect = [requests.Timeout("timed out"), success]
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
            retry_sleep_seconds=0,
        )

        result = CloudflareWorkersAIClient(config).chat(
            [{"role": "user", "content": "ping"}],
        )

        self.assertEqual(result, "ok after request timeout retry")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(0)

    @patch("entigram.cli_runner.cloudflare_ollama_proxy.requests.post")
    def test_raw_chat_streamed_aggregates_streaming_response(self, post):
        response = SimpleNamespace(
            ok=True,
            iter_lines=lambda: iter(
                [
                    b'data: {"choices":[{"delta":{"content":"hello "}}]}',
                    b'data: {"choices":[{"delta":{"content":"world"}}]}',
                    b"data: [DONE]",
                ]
            ),
        )
        post.return_value = response
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
        )

        result = CloudflareWorkersAIClient(config).raw_chat_streamed(
            [{"role": "user", "content": "ping"}],
        )

        self.assertEqual(result["choices"][0]["message"]["content"], "hello world")
        _, kwargs = post.call_args
        self.assertTrue(kwargs["json"]["stream"])

    def test_aggregate_streaming_chat_completion_supports_tool_call_deltas(self):
        result = aggregate_streaming_chat_completion(
            [
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "function": {"name": "Bash", "arguments": '{"cmd":'},
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": '"pwd"}'},
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                },
            ]
        )

        tool_call = result["choices"][0]["message"]["tool_calls"][0]
        self.assertEqual(tool_call["function"]["name"], "Bash")
        self.assertEqual(tool_call["function"]["arguments"], '{"cmd":"pwd"}')

    def test_ollama_helpers_shape_tags_generate_and_stream_chat(self):
        tags = tags_response(DEFAULT_MODEL_ALIAS)
        self.assertEqual(tags["models"][0]["name"], DEFAULT_MODEL_ALIAS)

        messages = prompt_to_messages("hello", system="be brief")
        self.assertEqual(
            messages,
            [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hello"},
            ],
        )

        stream = chat_stream_lines("@cf/zai-org/glm-5.2", "hello world")
        self.assertEqual(stream[0]["message"]["role"], "assistant")
        self.assertEqual(stream[0]["message"]["content"], "hello world")
        self.assertFalse(stream[0]["done"])
        self.assertTrue(stream[-1]["done"])

    def test_ollama_response_helpers_support_chat_and_generate_shapes(self):
        chat = non_stream_chat_response("@cf/zai-org/glm-5.2", "hello")
        generate = non_stream_generate_response("@cf/zai-org/glm-5.2", "hello")
        generate_stream = generate_stream_lines("@cf/zai-org/glm-5.2", "hello")

        self.assertEqual(chat["message"]["content"], "hello")
        self.assertTrue(chat["done"])
        self.assertEqual(generate["response"], "hello")
        self.assertTrue(generate["done"])
        self.assertEqual(generate_stream[0]["response"], "hello")
        self.assertFalse(generate_stream[0]["done"])
        self.assertTrue(generate_stream[-1]["done"])
        self.assertEqual(ps_response(), {"models": []})

    def test_make_handler_returns_proxy_handler_class(self):
        class FakeClient:
            def __init__(self):
                self.calls = []

            def chat(self, messages, model=None):
                self.calls.append((messages, model))
                return "hello through proxy"

        fake_client = FakeClient()
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
        )
        handler = make_handler(config, fake_client)

        self.assertEqual(handler.server_version, "EntigramCloudflareOllamaProxy/0.1")

    def test_handler_supports_ollama_head_probe(self):
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
        )
        handler = make_handler(config, object())

        class Probe:
            path = "/"

            def __init__(self):
                self.statuses = []
                self.ended = False

            def send_response(self, status):
                self.statuses.append(status)

            def end_headers(self):
                self.ended = True

        probe = Probe()
        handler.do_HEAD(probe)

        self.assertEqual(probe.statuses, [200])
        self.assertTrue(probe.ended)

    @patch("entigram.cli_runner.cloudflare_ollama_proxy.ThreadingHTTPServer")
    def test_serve_proxy_reports_port_conflict_readably(self, server):
        server.side_effect = OSError(48, "Address already in use")
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
        )

        with self.assertRaisesRegex(CloudflareProxyError, "already in use"):
            serve_proxy("127.0.0.1", 11435, config)

    @patch("builtins.print")
    @patch("entigram.cli_runner.cloudflare_ollama_proxy.subprocess.run")
    @patch("entigram.cli_runner.cloudflare_ollama_proxy.create_proxy_server")
    def test_launch_cloudflare_claude_starts_proxy_and_sets_ollama_host(self, create_server, run, _print):
        class FakeServer:
            server_address = ("127.0.0.1", 45678)

            def __init__(self):
                self.shutdown_called = False
                self.close_called = False

            def serve_forever(self):
                return None

            def shutdown(self):
                self.shutdown_called = True

            def server_close(self):
                self.close_called = True

        fake_server = FakeServer()
        create_server.return_value = fake_server
        run.return_value = SimpleNamespace(returncode=0)
        config = CloudflareProxyConfig(
            account_id="account-id",
            api_token="token",
            model="@cf/zai-org/glm-5.2",
            model_alias=DEFAULT_MODEL_ALIAS,
        )

        result = launch_cloudflare_claude("127.0.0.1", 0, config)

        self.assertEqual(result, 0)
        create_server.assert_called_once_with("127.0.0.1", 0, config, ANY)
        run.assert_called_once()
        self.assertEqual(
            run.call_args.args[0],
            ["ollama", "launch", "claude", "--model", DEFAULT_MODEL_ALIAS],
        )
        self.assertEqual(run.call_args.kwargs["env"]["OLLAMA_HOST"], "http://127.0.0.1:45678")
        self.assertTrue(fake_server.shutdown_called)
        self.assertTrue(fake_server.close_called)

    @patch("builtins.print")
    @patch("entigram.cli_runner.cloudflare_ollama_proxy.subprocess.run")
    @patch("entigram.cli_runner.cloudflare_ollama_proxy.create_proxy_server")
    def test_launch_cloudflare_claude_guides_missing_ollama_setup(self, create_server, run, _print):
        class FakeServer:
            server_address = ("127.0.0.1", 45678)

            def __init__(self):
                self.shutdown_called = False
                self.close_called = False

            def serve_forever(self):
                return None

            def shutdown(self):
                self.shutdown_called = True

            def server_close(self):
                self.close_called = True

        fake_server = FakeServer()
        create_server.return_value = fake_server
        run.side_effect = FileNotFoundError("ollama")
        config = CloudflareProxyConfig(account_id="account-id", api_token="token")

        with self.assertRaisesRegex(CloudflareProxyError, "Could not find `ollama`") as ctx:
            launch_cloudflare_claude("127.0.0.1", 0, config)

        self.assertIn("etg cloudflare-claude", str(ctx.exception))
        self.assertTrue(fake_server.shutdown_called)
        self.assertTrue(fake_server.close_called)

    def test_parse_tool_arguments_tolerates_malformed_json(self):
        self.assertEqual(parse_tool_arguments(None), {})
        self.assertEqual(parse_tool_arguments(""), {})
        self.assertEqual(parse_tool_arguments("not json"), {})
        self.assertEqual(parse_tool_arguments('{"cmd": "pwd"}'), {"cmd": "pwd"})
        self.assertEqual(parse_tool_arguments("[1, 2]"), {})
        self.assertEqual(parse_tool_arguments({"already": "dict"}), {"already": "dict"})


if __name__ == "__main__":
    unittest.main()
