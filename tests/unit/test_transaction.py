"""Unit tests for Transaction infrastructure."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from resonance.infrastructure.transaction import Transaction, FileOperation, TransactionManager


class TestFileOperation:
    """Test FileOperation functionality."""

    def test_file_operation_creation(self):
        """Test creating a FileOperation."""
        op = FileOperation(
            op_type="move",
            path=Path("/test/file.mp3"),
            original_path=Path("/test/original.mp3"),
            backup_path=Path("/tmp/backup.mp3")
        )

        assert op.op_type == "move"
        assert op.path == Path("/test/file.mp3")
        assert op.original_path == Path("/test/original.mp3")
        assert op.backup_path == Path("/tmp/backup.mp3")

    def test_file_operation_to_dict(self):
        """Test converting FileOperation to dict."""
        op = FileOperation(
            op_type="move",
            path=Path("/test/file.mp3"),
            original_path=Path("/test/original.mp3"),
            backup_path=Path("/tmp/backup.mp3"),
            metadata={"size": 12345}
        )

        data = op.to_dict()

        assert data["op_type"] == "move"
        assert data["path"] == "/test/file.mp3"
        assert data["original_path"] == "/test/original.mp3"
        assert data["backup_path"] == "/tmp/backup.mp3"
        assert data["metadata"]["size"] == 12345

    def test_file_operation_from_dict(self):
        """Test creating FileOperation from dict."""
        data = {
            "op_type": "move",
            "path": "/test/file.mp3",
            "original_path": "/test/original.mp3",
            "backup_path": "/tmp/backup.mp3",
            "metadata": {"size": 12345},
            "timestamp": "2023-01-01T00:00:00"
        }

        op = FileOperation.from_dict(data)

        assert op.op_type == "move"
        assert op.path == Path("/test/file.mp3")
        assert op.original_path == Path("/test/original.mp3")
        assert op.backup_path == Path("/tmp/backup.mp3")
        assert op.metadata["size"] == 12345


class TestTransaction:
    """Test Transaction functionality."""

    def test_transaction_init(self):
        """Test transaction initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            txn = Transaction(temp_dir=Path(temp_dir))

            assert txn.operations == []
            assert txn.committed is False
            assert txn.rolled_back is False
            assert txn.txn_dir.exists()

    def test_transaction_context_success(self):
        """Test successful transaction context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with Transaction(temp_dir=Path(temp_dir)) as txn:
                assert isinstance(txn, Transaction)
                # Transaction should succeed
                pass

            assert txn.committed is True
            assert txn.rolled_back is False

    def test_transaction_context_failure(self):
        """Test failed transaction context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with Transaction(temp_dir=Path(temp_dir)) as txn:
                    raise ValueError("Test error")
            except ValueError:
                pass

            assert txn.committed is False
            assert txn.rolled_back is True

    def test_move_file_success(self):
        """Test successful file move operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source file
            src = temp_path / "source.mp3"
            src.write_text("test content")

            # Create destination
            dst = temp_path / "dest.mp3"

            with Transaction(temp_dir=temp_path) as txn:
                txn.move_file(src, dst)

                # File should be moved
                assert not src.exists()
                assert dst.exists()
                assert dst.read_text() == "test content"

            # Transaction should be committed and cleaned up
            assert txn.committed is True

    def test_move_file_with_existing_destination(self):
        """Test file move when destination already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source and destination files
            src = temp_path / "source.mp3"
            src.write_text("source content")

            dst = temp_path / "dest.mp3"
            dst.write_text("dest content")

            with Transaction(temp_dir=temp_path) as txn:
                txn.move_file(src, dst)

                # Source should be gone, destination should have source content
                assert not src.exists()
                assert dst.exists()
                assert dst.read_text() == "source content"

            assert txn.committed is True

    def test_move_file_rollback(self):
        """Test file move rollback on failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source file
            src = temp_path / "source.mp3"
            src.write_text("test content")

            try:
                with Transaction(temp_dir=temp_path) as txn:
                    txn.move_file(src, temp_path / "dest.mp3")
                    raise ValueError("Test failure")
            except ValueError:
                pass

            # File should be back to original location
            assert src.exists()
            assert src.read_text() == "test content"
            assert txn.rolled_back is True

    def test_create_file_success(self):
        """Test successful file creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            new_file = temp_path / "new_file.txt"

            with Transaction(temp_dir=temp_path) as txn:
                txn.create_file(new_file, b"test content")

                assert new_file.exists()
                assert new_file.read_bytes() == b"test content"

            assert txn.committed is True

    def test_create_file_rollback(self):
        """Test file creation rollback."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            new_file = temp_path / "new_file.txt"

            try:
                with Transaction(temp_dir=temp_path) as txn:
                    txn.create_file(new_file, b"test content")
                    raise ValueError("Test failure")
            except ValueError:
                pass

            # File should not exist after rollback
            assert not new_file.exists()
            assert txn.rolled_back is True

    def test_delete_file_success(self):
        """Test successful file deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file to delete
            file_to_delete = temp_path / "to_delete.txt"
            file_to_delete.write_text("content")

            with Transaction(temp_dir=temp_path) as txn:
                txn.delete_file(file_to_delete)

                assert not file_to_delete.exists()

            assert txn.committed is True

    def test_delete_file_rollback(self):
        """Test file deletion rollback."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file to delete
            file_to_delete = temp_path / "to_delete.txt"
            file_to_delete.write_text("content")

            try:
                with Transaction(temp_dir=temp_path) as txn:
                    txn.delete_file(file_to_delete)
                    raise ValueError("Test failure")
            except ValueError:
                pass

            # File should be restored after rollback
            assert file_to_delete.exists()
            assert file_to_delete.read_text() == "content"
            assert txn.rolled_back is True

    def test_tag_write_success(self):
        """Test successful tag write operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file to modify
            audio_file = temp_path / "track.mp3"
            audio_file.write_text("original content")

            with Transaction(temp_dir=temp_path) as txn:
                def write_tags():
                    audio_file.write_text("modified content")

                txn.tag_write(audio_file, write_tags)

                assert audio_file.read_text() == "modified content"

            assert txn.committed is True

    def test_tag_write_rollback(self):
        """Test tag write rollback on failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file to modify
            audio_file = temp_path / "track.mp3"
            audio_file.write_text("original content")

            try:
                with Transaction(temp_dir=temp_path) as txn:
                    def write_tags():
                        audio_file.write_text("modified content")

                    txn.tag_write(audio_file, write_tags)
                    raise ValueError("Test failure")
            except ValueError:
                pass

            # File should be restored to original content
            assert audio_file.read_text() == "original content"
            assert txn.rolled_back is True

    def test_transaction_log_persistence(self):
        """Test that transaction logs are saved during operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with Transaction(temp_dir=temp_path) as txn:
                # Create a simple file operation to trigger log creation
                src = temp_path / "test_src.txt"
                src.write_text("test")
                dst = temp_path / "test_dst.txt"

                txn.move_file(src, dst)

                # Log should exist during transaction
                assert txn.log_path.exists()
                assert txn.log_path.read_text()  # Should have content

            # After successful commit, transaction directory is cleaned up
            # (Log is removed as part of successful completion)


class TestTransactionManager:
    """Test TransactionManager functionality."""

    def test_transaction_manager_init(self):
        """Test TransactionManager initialization."""
        manager = TransactionManager()
        assert manager.temp_dir.name == "audio-meta-transactions"

    def test_transaction_manager_custom_temp_dir(self):
        """Test TransactionManager with custom temp directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_temp = Path(temp_dir) / "custom_txn_dir"
            manager = TransactionManager(temp_dir=custom_temp)
            assert manager.temp_dir == custom_temp

    def test_recover_incomplete_no_transactions(self):
        """Test recovering when no incomplete transactions exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TransactionManager(temp_dir=Path(temp_dir))

            recovered = manager.recover_incomplete()
            assert recovered == 0

    def test_recover_incomplete_with_transaction_dir(self):
        """Test recovering incomplete transactions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manager = TransactionManager(temp_dir=temp_path)

            # Create a fake incomplete transaction directory
            txn_dir = temp_path / "incomplete_txn"
            txn_dir.mkdir()

            log_file = txn_dir / "transaction.json"
            log_file.write_text('{"transaction_id": "test", "operations": []}')

            recovered = manager.recover_incomplete()
            assert recovered == 1

    def test_transaction_with_multiple_operations(self):
        """Test transaction with multiple file operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple files for operations
            src1 = temp_path / "source1.mp3"
            src1.write_text("content1")
            dst1 = temp_path / "dest1.mp3"

            src2 = temp_path / "source2.mp3"
            src2.write_text("content2")
            dst2 = temp_path / "dest2.mp3"

            with Transaction(temp_dir=temp_path) as txn:
                txn.move_file(src1, dst1)
                txn.move_file(src2, dst2)

                # Both files should be moved
                assert not src1.exists()
                assert not src2.exists()
                assert dst1.exists()
                assert dst2.exists()

            assert txn.committed is True

    def test_transaction_tag_write_with_exception_in_write_func(self):
        """Test tag write when the write function itself throws an exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            audio_file = temp_path / "track.mp3"
            audio_file.write_text("original")

            try:
                with Transaction(temp_dir=temp_path) as txn:
                    def failing_write():
                        raise IOError("Disk full")

                    txn.tag_write(audio_file, failing_write)
            except IOError:
                pass

            # Transaction should be rolled back, file restored
            assert audio_file.read_text() == "original"
            assert txn.rolled_back is True

    def test_transaction_move_nonexistent_file(self):
        """Test attempting to move a non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            nonexistent = temp_path / "nonexistent.mp3"
            destination = temp_path / "dest.mp3"

            with pytest.raises(FileNotFoundError):
                with Transaction(temp_dir=temp_path) as txn:
                    txn.move_file(nonexistent, destination)

    def test_transaction_create_existing_file(self):
        """Test attempting to create a file that already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            existing_file = temp_path / "existing.txt"
            existing_file.write_text("existing content")

            with pytest.raises(FileExistsError):
                with Transaction(temp_dir=temp_path) as txn:
                    txn.create_file(existing_file, b"new content")

    def test_transaction_delete_nonexistent_file(self):
        """Test attempting to delete a non-existent file (should not fail)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            nonexistent = temp_path / "nonexistent.mp3"

            with Transaction(temp_dir=temp_path) as txn:
                txn.delete_file(nonexistent)  # Should not raise

            assert txn.committed is True

    def test_transaction_rollback_with_multiple_operations(self):
        """Test rollback with multiple operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Set up files
            src1 = temp_path / "src1.mp3"
            src1.write_text("content1")
            dst1 = temp_path / "dst1.mp3"

            src2 = temp_path / "src2.mp3"
            src2.write_text("content2")

            try:
                with Transaction(temp_dir=temp_path) as txn:
                    txn.move_file(src1, dst1)
                    txn.delete_file(src2)
                    raise ValueError("Test failure")
            except ValueError:
                pass

            # Both operations should be rolled back
            assert src1.exists() and src1.read_text() == "content1"
            assert src2.exists() and src2.read_text() == "content2"
            assert not dst1.exists()
            assert txn.rolled_back is True

    def test_transaction_context_double_commit(self):
        """Test that committing an already committed transaction does nothing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with Transaction(temp_dir=Path(temp_dir)) as txn:
                pass  # Normal completion

            # Transaction is already committed
            assert txn.committed is True

            # Calling commit again should do nothing
            txn.commit()
            assert txn.committed is True

    def test_transaction_context_double_rollback(self):
        """Test that rolling back an already rolled back transaction does nothing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with Transaction(temp_dir=Path(temp_dir)) as txn:
                    raise ValueError("Test")
            except ValueError:
                pass

            # Transaction is already rolled back
            assert txn.rolled_back is True

            # Calling rollback again should do nothing
            txn.rollback()
            assert txn.rolled_back is True

    def test_file_operation_serialization_edge_cases(self):
        """Test FileOperation serialization with None values."""
        # Test with None backup_path
        op = FileOperation(
            op_type="create",
            path=Path("/test/file.txt"),
            backup_path=None,
            original_path=None
        )

        data = op.to_dict()
        assert data["backup_path"] is None
        assert data["original_path"] is None

        # Deserialize back
        op2 = FileOperation.from_dict(data)
        assert op2.backup_path is None
        assert op2.original_path is None

    def test_transaction_custom_id(self):
        """Test transaction with custom transaction ID."""
        custom_id = "my_custom_txn_123"
        with tempfile.TemporaryDirectory() as temp_dir:
            txn = Transaction(temp_dir=Path(temp_dir), transaction_id=custom_id)

            assert txn.transaction_id == custom_id
            assert custom_id in str(txn.txn_dir)

    def test_transaction_log_with_special_characters(self):
        """Test transaction logging with special characters in paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            special_file = temp_path / "file with spaces & special chars.mp3"
            special_file.write_text("content")

            dest_file = temp_path / "dest.mp3"

            with Transaction(temp_dir=temp_path) as txn:
                txn.move_file(special_file, dest_file)

                # Log should handle special characters properly
                assert txn.log_path.exists()
                log_content = txn.log_path.read_text()
                assert "file with spaces & special chars.mp3" in log_content

    def test_transaction_manager_recovery_with_malformed_log(self):
        """Test recovery when transaction log is malformed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manager = TransactionManager(temp_dir=temp_path)

            # Create a directory with malformed JSON log
            txn_dir = temp_path / "bad_txn"
            txn_dir.mkdir()
            log_file = txn_dir / "transaction.json"
            log_file.write_text("invalid json content")

            # Recovery should handle the error gracefully
            recovered = manager.recover_incomplete()
            assert recovered == 0  # Should not count as recovered due to error
