"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { UIMessage } from "./ChatMessages";
import { saveAs } from "file-saver";

interface SaveChatDialogProps {
  messages: UIMessage[];
  open: boolean;
  setOpen: (value: boolean) => void;
}

const SaveChatDialog: React.FC<SaveChatDialogProps> = ({ messages, open, setOpen }) => {
  const [fileName, setFileName] = useState("chat");
  const [fileType, setFileType] = useState<"txt" | "pdf" | "docx">("txt");

  const handleDownload = () => {
    const content = messages
      .map(m => `${m.role === "user" ? "User" : "Assistant"}: ${m.content}`)
      .join("\n\n");

    const blob = new Blob([content], {
      type:
        fileType === "pdf"
          ? "application/pdf"
          : fileType === "docx"
          ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          : "text/plain",
    });

    const fileExt = fileType;
    try {
      saveAs(blob, `${fileName}.${fileExt}`);
    } catch {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${fileName}.${fileExt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }

    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Save Chat</DialogTitle>
          <DialogDescription>Export the conversation history</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="chat-file-name">File Name</Label>
            <Input
              id="chat-file-name"
              value={fileName}
              onChange={e => setFileName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="chat-file-type">File Type</Label>
            <Select value={fileType} onValueChange={value => setFileType(value as any)}>
              <SelectTrigger id="chat-file-type" className="w-full">
                <SelectValue>{fileType}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="txt">txt</SelectItem>
                <SelectItem value="pdf">pdf</SelectItem>
                <SelectItem value="docx">docx</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" onClick={handleDownload}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SaveChatDialog;