export type Role = "user" | "assistant";

export type Message = {
  id: string;
  role: Role;
  text: string;
};
