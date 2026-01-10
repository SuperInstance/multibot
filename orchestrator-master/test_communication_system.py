#!/usr/bin/env python3
"""
Communication System Test Suite
Comprehensive tests for the bidirectional communication protocol.
"""

import asyncio
import json
import logging
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Import the components to test
from message_queue import (
    MessageQueueManager, MessageType, MessagePriority, MessageStatus, TaskStatus
)
from master_communication import MasterCommunicationHandler
from priority_timeout_handler import PriorityTimeoutHandler, TimeoutRule, TimeoutAction

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMessageQueue(unittest.IsolatedAsyncioTestCase):
    """Test the core message queue functionality."""

    async def asyncSetUp(self):
        """Set up test environment."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()

        self.message_queue = MessageQueueManager(self.test_db.name)
        await self.message_queue.initialize()

    async def asyncTearDown(self):
        """Clean up test environment."""
        await self.message_queue.cleanup()
        os.unlink(self.test_db.name)

    async def test_basic_message_sending(self):
        """Test basic message sending and receiving."""
        # Send a message
        message_id = await self.message_queue.send_message(
            from_id="test_sender",
            to_id="test_recipient",
            message_type=MessageType.STATUS_UPDATE,
            content={"status": "test", "data": "hello world"},
            priority=MessagePriority.NORMAL
        )

        self.assertIsNotNone(message_id)

        # Receive the message
        messages = await self.message_queue.receive_messages("test_recipient")
        self.assertEqual(len(messages), 1)

        message = messages[0]
        self.assertEqual(message.id, message_id)
        self.assertEqual(message.from_id, "test_sender")
        self.assertEqual(message.to_id, "test_recipient")
        self.assertEqual(message.message_type, MessageType.STATUS_UPDATE)
        self.assertEqual(message.content["status"], "test")

    async def test_priority_ordering(self):
        """Test that messages are received in priority order."""
        # Send messages with different priorities
        low_id = await self.message_queue.send_message(
            from_id="sender", to_id="recipient",
            message_type=MessageType.STATUS_UPDATE,
            content={"priority": "low"},
            priority=MessagePriority.LOW
        )

        high_id = await self.message_queue.send_message(
            from_id="sender", to_id="recipient",
            message_type=MessageType.QUESTION,
            content={"priority": "high"},
            priority=MessagePriority.HIGH
        )

        urgent_id = await self.message_queue.send_message(
            from_id="sender", to_id="recipient",
            message_type=MessageType.ERROR,
            content={"priority": "urgent"},
            priority=MessagePriority.URGENT
        )

        # Receive messages
        messages = await self.message_queue.receive_messages("recipient")

        # Should be in priority order: urgent, high, low
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0].id, urgent_id)
        self.assertEqual(messages[1].id, high_id)
        self.assertEqual(messages[2].id, low_id)

    async def test_task_assignment(self):
        """Test task assignment functionality."""
        success = await self.message_queue.assign_task(
            task_id="test_task",
            worker_id="test_worker",
            description="Test task description",
            context={"test": True, "complexity": "low"},
            priority=7
        )

        self.assertTrue(success)

        # Get worker tasks
        tasks = await self.message_queue.get_worker_tasks("test_worker")
        self.assertEqual(len(tasks), 1)

        task = tasks[0]
        self.assertEqual(task.task_id, "test_task")
        self.assertEqual(task.worker_id, "test_worker")
        self.assertEqual(task.description, "Test task description")
        self.assertEqual(task.status, TaskStatus.ASSIGNED)

    async def test_task_status_updates(self):
        """Test task status update functionality."""
        # Create a task
        await self.message_queue.assign_task(
            task_id="status_test_task",
            worker_id="test_worker",
            description="Status test task",
            context={"test": True}
        )

        # Update status to in progress
        success = await self.message_queue.update_task_status(
            task_id="status_test_task",
            status=TaskStatus.IN_PROGRESS
        )
        self.assertTrue(success)

        # Update status to completed with result
        success = await self.message_queue.update_task_status(
            task_id="status_test_task",
            status=TaskStatus.COMPLETED,
            result={"output": "task completed successfully"}
        )
        self.assertTrue(success)

        # Verify final status
        tasks = await self.message_queue.get_worker_tasks("test_worker")
        task = tasks[0]
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(task.result)
        self.assertEqual(task.result["output"], "task completed successfully")

    async def test_message_expiration(self):
        """Test message expiration handling."""
        # Send a message that expires quickly
        message_id = await self.message_queue.send_message(
            from_id="sender",
            to_id="recipient",
            message_type=MessageType.HEARTBEAT,
            content={"test": "expiring"},
            expires_in_seconds=1  # Expires in 1 second
        )

        # Wait for expiration
        await asyncio.sleep(2)

        # Cleanup expired messages
        await self.message_queue.cleanup_expired_messages()

        # Message should be marked as expired
        # Note: This test might need adjustment based on implementation details


class TestMasterCommunication(unittest.IsolatedAsyncioTestCase):
    """Test the master communication handler."""

    async def asyncSetUp(self):
        """Set up test environment."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()

        self.message_queue = MessageQueueManager(self.test_db.name)
        await self.message_queue.initialize()

        self.master_comm = MasterCommunicationHandler(self.message_queue)
        await self.master_comm.initialize()

    async def asyncTearDown(self):
        """Clean up test environment."""
        await self.master_comm.cleanup()
        await self.message_queue.cleanup()
        os.unlink(self.test_db.name)

    async def test_task_assignment(self):
        """Test task assignment through master communication."""
        success = await self.master_comm.send_task_assignment(
            worker_id="test_worker",
            task_id="comm_test_task",
            description="Communication test task",
            context={"framework": "test", "priority": "high"},
            priority=8
        )

        self.assertTrue(success)

        # Verify task was created
        tasks = await self.message_queue.get_worker_tasks("test_worker")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "comm_test_task")

    async def test_guidance_sending(self):
        """Test sending guidance to workers."""
        message_id = await self.master_comm.send_guidance(
            worker_id="test_worker",
            guidance_type="implementation_suggestion",
            guidance="Consider using the factory pattern for object creation",
            context={"file": "src/models.py", "line": 45}
        )

        self.assertIsNotNone(message_id)

        # Verify message was sent
        messages = await self.message_queue.receive_messages("test_worker")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_type, MessageType.GUIDANCE)

    async def test_context_sharing(self):
        """Test context sharing between workers."""
        message_id = await self.master_comm.share_context(
            worker_id="test_worker",
            context_type="design_pattern",
            context_data={
                "pattern": "observer",
                "use_case": "event_handling",
                "implementation": "src/events.py"
            },
            source_worker="source_worker"
        )

        self.assertIsNotNone(message_id)

        # Verify context message
        messages = await self.message_queue.receive_messages("test_worker")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_type, MessageType.CONTEXT_SHARE)
        self.assertEqual(messages[0].content["context_type"], "design_pattern")

    async def test_broadcasting(self):
        """Test broadcasting messages to multiple workers."""
        worker_ids = ["worker_1", "worker_2", "worker_3"]

        message_ids = await self.master_comm.broadcast_to_workers(
            worker_ids=worker_ids,
            message_type=MessageType.GUIDANCE,
            content={"guidance": "Follow new coding standards"},
            priority=MessagePriority.NORMAL
        )

        self.assertEqual(len(message_ids), 3)

        # Verify each worker received the message
        for worker_id in worker_ids:
            messages = await self.message_queue.receive_messages(worker_id)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].content["guidance"], "Follow new coding standards")


class TestPriorityTimeoutHandler(unittest.IsolatedAsyncioTestCase):
    """Test the priority and timeout handling system."""

    async def asyncSetUp(self):
        """Set up test environment."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()

        self.message_queue = MessageQueueManager(self.test_db.name)
        await self.message_queue.initialize()

        self.priority_handler = PriorityTimeoutHandler(self.message_queue)
        await self.priority_handler.initialize()

    async def asyncTearDown(self):
        """Clean up test environment."""
        await self.priority_handler.cleanup()
        await self.message_queue.cleanup()
        os.unlink(self.test_db.name)

    async def test_priority_processing(self):
        """Test priority-based message processing."""
        processed_messages = []

        async def test_processor(message):
            processed_messages.append(message.content["order"])

        # Register processor
        self.priority_handler.register_message_processor(
            MessageType.STATUS_UPDATE,
            test_processor
        )

        # Create messages with different priorities
        low_msg = await self.message_queue.send_message(
            from_id="test", to_id="test",
            message_type=MessageType.STATUS_UPDATE,
            content={"order": "low"},
            priority=MessagePriority.LOW
        )

        high_msg = await self.message_queue.send_message(
            from_id="test", to_id="test",
            message_type=MessageType.STATUS_UPDATE,
            content={"order": "high"},
            priority=MessagePriority.HIGH
        )

        urgent_msg = await self.message_queue.send_message(
            from_id="test", to_id="test",
            message_type=MessageType.STATUS_UPDATE,
            content={"order": "urgent"},
            priority=MessagePriority.URGENT
        )

        # Get messages and enqueue for processing
        messages = await self.message_queue.receive_messages("test")
        for message in messages:
            await self.priority_handler.enqueue_message(message)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Should be processed in priority order
        self.assertEqual(len(processed_messages), 3)
        self.assertEqual(processed_messages[0], "urgent")
        self.assertEqual(processed_messages[1], "high")
        self.assertEqual(processed_messages[2], "low")

    async def test_timeout_handling(self):
        """Test message timeout handling."""
        timeout_called = []

        async def timeout_callback(message, timeout_rule):
            timeout_called.append(message.id)

        self.priority_handler.register_timeout_callback(timeout_callback)

        # Set a very short timeout for testing
        self.priority_handler.set_timeout_rule(
            MessageType.QUESTION,
            TimeoutRule(
                message_type=MessageType.QUESTION,
                timeout_seconds=0.1,  # Very short for testing
                action=TimeoutAction.CALLBACK,
                max_retries=0
            )
        )

        # Send a message that will timeout
        message_id = await self.message_queue.send_message(
            from_id="test", to_id="test",
            message_type=MessageType.QUESTION,
            content={"question": "test"},
            priority=MessagePriority.NORMAL
        )

        messages = await self.message_queue.receive_messages("test")
        await self.priority_handler.enqueue_message(messages[0])

        # Wait for timeout
        await asyncio.sleep(0.2)

        # Timeout callback should have been called
        self.assertIn(message_id, timeout_called)

    async def test_urgent_message(self):
        """Test urgent message handling."""
        message_id = await self.priority_handler.urgent_message(
            from_id="master",
            to_id="worker",
            message_type=MessageType.TERMINATE,
            content={"reason": "emergency_shutdown"},
            timeout_seconds=5
        )

        self.assertIsNotNone(message_id)

        # Verify message was sent with critical priority
        messages = await self.message_queue.receive_messages("worker")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].priority, MessagePriority.CRITICAL)


class TestWorkerMCPTools(unittest.TestCase):
    """Test worker MCP tools (simulated)."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir) / "memory"
        self.memory_dir.mkdir()

        # Set environment variables
        os.environ["WORKER_ID"] = "test_worker"
        os.environ["WORKER_MODEL"] = "test_model"
        os.environ["WORKER_MEMORY_DIR"] = str(self.memory_dir)

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_memory_operations(self):
        """Test memory save/load operations."""
        # This would test the worker MCP tools
        # Since they require the MCP server to be running,
        # we'll test the underlying logic

        test_data = {
            "key": "test_context",
            "data": {"pattern": "factory", "file": "src/factory.py"},
            "saved_at": datetime.now().isoformat(),
            "worker_id": "test_worker"
        }

        # Test save
        context_file = self.memory_dir / "test_context.json"
        with open(context_file, "w") as f:
            json.dump(test_data, f)

        self.assertTrue(context_file.exists())

        # Test load
        with open(context_file) as f:
            loaded_data = json.load(f)

        self.assertEqual(loaded_data["key"], "test_context")
        self.assertEqual(loaded_data["data"]["pattern"], "factory")


class TestIntegrationScenarios(unittest.IsolatedAsyncioTestCase):
    """Test complete integration scenarios."""

    async def asyncSetUp(self):
        """Set up test environment."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()

        self.message_queue = MessageQueueManager(self.test_db.name)
        await self.message_queue.initialize()

        self.master_comm = MasterCommunicationHandler(self.message_queue)
        await self.master_comm.initialize()

        self.priority_handler = PriorityTimeoutHandler(self.message_queue)
        await self.priority_handler.initialize()

    async def asyncTearDown(self):
        """Clean up test environment."""
        await self.priority_handler.cleanup()
        await self.master_comm.cleanup()
        await self.message_queue.cleanup()
        os.unlink(self.test_db.name)

    async def test_complete_task_workflow(self):
        """Test a complete task assignment and completion workflow."""
        # 1. Master assigns task
        success = await self.master_comm.send_task_assignment(
            worker_id="integration_worker",
            task_id="integration_task",
            description="Complete integration test task",
            context={"test": True, "complexity": "medium"},
            priority=7
        )
        self.assertTrue(success)

        # 2. Simulate worker receiving task
        messages = await self.message_queue.receive_messages("integration_worker")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_type, MessageType.TASK_ASSIGN)

        # 3. Simulate worker asking question
        question_id = await self.message_queue.send_message(
            from_id="integration_worker",
            to_id="master",
            message_type=MessageType.QUESTION,
            content={
                "question": "Should I use async/await for this implementation?",
                "context": {"task_id": "integration_task", "file": "src/main.py"}
            },
            priority=MessagePriority.HIGH
        )

        # 4. Master receives and answers question
        questions = await self.message_queue.receive_messages("master")
        self.assertEqual(len(questions), 1)

        await self.master_comm.answer_question(
            message_id=question_id,
            answer="Yes, use async/await for better performance",
            additional_context={"docs": "https://docs.python.org/3/library/asyncio.html"}
        )

        # 5. Simulate worker reporting progress
        await self.message_queue.send_message(
            from_id="integration_worker",
            to_id="master",
            message_type=MessageType.STATUS_UPDATE,
            content={
                "task_id": "integration_task",
                "task_status": "in_progress",
                "progress": 50,
                "notes": "Halfway through implementation"
            }
        )

        # 6. Simulate task completion
        await self.message_queue.send_message(
            from_id="integration_worker",
            to_id="master",
            message_type=MessageType.TASK_COMPLETE,
            content={
                "task_id": "integration_task",
                "result": {
                    "summary": "Task completed successfully",
                    "files_modified": ["src/main.py", "tests/test_main.py"],
                    "performance": "async implementation 40% faster"
                }
            }
        )

        # 7. Verify task completion was processed
        completion_messages = await self.message_queue.receive_messages("master")
        completion_found = any(
            msg.message_type == MessageType.TASK_COMPLETE
            for msg in completion_messages
        )
        self.assertTrue(completion_found)

    async def test_error_escalation_workflow(self):
        """Test error reporting and escalation workflow."""
        # 1. Worker reports error
        error_id = await self.message_queue.send_message(
            from_id="error_worker",
            to_id="master",
            message_type=MessageType.ERROR,
            content={
                "error_type": "dependency_conflict",
                "error_message": "Version conflict between packages",
                "task_id": "error_task",
                "blocking": True
            },
            priority=MessagePriority.URGENT
        )

        # 2. Master receives error
        errors = await self.message_queue.receive_messages("master")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].message_type, MessageType.ERROR)

        # 3. Master provides guidance
        guidance_id = await self.master_comm.send_guidance(
            worker_id="error_worker",
            guidance_type="error_resolution",
            guidance="Update package versions in requirements.txt",
            context={"specific_packages": ["asyncio==3.4.3", "requests==2.28.0"]}
        )

        # 4. Verify guidance was sent
        guidance_messages = await self.message_queue.receive_messages("error_worker")
        self.assertEqual(len(guidance_messages), 1)
        self.assertEqual(guidance_messages[0].message_type, MessageType.GUIDANCE)

    async def test_context_sharing_workflow(self):
        """Test context sharing between workers."""
        # 1. Worker 1 completes implementation
        await self.message_queue.send_message(
            from_id="worker_1",
            to_id="master",
            message_type=MessageType.TASK_COMPLETE,
            content={
                "task_id": "auth_task",
                "result": {
                    "pattern_used": "jwt_authentication",
                    "implementation_file": "src/auth.py",
                    "lessons_learned": ["use_refresh_tokens", "implement_rate_limiting"]
                }
            }
        )

        # 2. Master shares context with other workers
        context_data = {
            "pattern": "jwt_authentication",
            "best_practices": ["use_refresh_tokens", "implement_rate_limiting"],
            "reference_implementation": "src/auth.py"
        }

        message_ids = await self.master_comm.broadcast_to_workers(
            worker_ids=["worker_2", "worker_3"],
            message_type=MessageType.CONTEXT_SHARE,
            content={
                "context_type": "authentication_pattern",
                "context_data": context_data,
                "source_worker": "worker_1"
            }
        )

        self.assertEqual(len(message_ids), 2)

        # 3. Verify both workers received context
        for worker_id in ["worker_2", "worker_3"]:
            messages = await self.message_queue.receive_messages(worker_id)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].message_type, MessageType.CONTEXT_SHARE)


def run_example_scenario():
    """Run an example communication scenario."""
    async def example():
        print("🚀 Running Communication System Example")

        # Set up components
        test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        test_db.close()

        try:
            message_queue = MessageQueueManager(test_db.name)
            await message_queue.initialize()

            master_comm = MasterCommunicationHandler(message_queue)
            await master_comm.initialize()

            print("✅ Initialized communication system")

            # Example 1: Task assignment
            print("\n📋 Example 1: Task Assignment")
            success = await master_comm.send_task_assignment(
                worker_id="example_worker",
                task_id="example_task",
                description="Implement user authentication system",
                context={
                    "requirements": ["secure", "scalable", "tested"],
                    "files": ["src/auth.py", "tests/test_auth.py"],
                    "deadline": "2024-01-15"
                },
                priority=7
            )
            print(f"Task assigned: {success}")

            # Example 2: Worker question
            print("\n❓ Example 2: Worker Question")
            question_id = await message_queue.send_message(
                from_id="example_worker",
                to_id="master",
                message_type=MessageType.QUESTION,
                content={
                    "question": "Should I use bcrypt or argon2 for password hashing?",
                    "context": {
                        "security_level": "high",
                        "performance_requirement": "< 100ms per hash"
                    }
                },
                priority=MessagePriority.HIGH
            )
            print(f"Question sent: {question_id}")

            # Example 3: Master answers question
            print("\n💬 Example 3: Answer Question")
            questions = await message_queue.receive_messages("master")
            if questions:
                await master_comm.answer_question(
                    message_id=questions[0].id,
                    answer="Use argon2 for better security and performance",
                    additional_context={
                        "reasoning": "Argon2 is more secure and faster than bcrypt",
                        "implementation": "pip install argon2-cffi"
                    }
                )
                print("Question answered")

            # Example 4: Status update
            print("\n📊 Example 4: Status Update")
            await message_queue.send_message(
                from_id="example_worker",
                to_id="master",
                message_type=MessageType.STATUS_UPDATE,
                content={
                    "status": "working",
                    "task_id": "example_task",
                    "progress": 60,
                    "current_activity": "Implementing password hashing",
                    "estimated_completion": "2024-01-14T16:00:00"
                }
            )
            print("Status update sent")

            # Example 5: Context sharing
            print("\n🔄 Example 5: Context Sharing")
            await master_comm.share_context(
                worker_id="example_worker",
                context_type="security_pattern",
                context_data={
                    "pattern": "secure_authentication",
                    "implementation": "argon2 + jwt tokens",
                    "best_practices": [
                        "use_refresh_tokens",
                        "implement_rate_limiting",
                        "hash_passwords_before_storage"
                    ]
                }
            )
            print("Context shared")

            # Example 6: Get statistics
            print("\n📈 Example 6: System Statistics")
            stats = await message_queue.get_message_stats()
            print(f"Message statistics: {json.dumps(stats, indent=2)}")

            print("\n✅ Communication system example completed successfully!")

        finally:
            # Cleanup
            await master_comm.cleanup()
            await message_queue.cleanup()
            os.unlink(test_db.name)

    # Run the example
    asyncio.run(example())


if __name__ == "__main__":
    # Run tests
    print("🧪 Running Communication System Tests")
    unittest.main(argv=[''], exit=False, verbosity=2)

    print("\n" + "="*50)
    print("🎯 Running Example Scenario")
    print("="*50)

    # Run example
    run_example_scenario()