#[cfg(not(target_arch = "wasm32"))]
pub use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

#[cfg(target_arch = "wasm32")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum KeyCode {
    Backspace,
    Enter,
    Esc,
    Char(char),
}

#[cfg(target_arch = "wasm32")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct KeyModifiers(u8);

#[cfg(target_arch = "wasm32")]
impl KeyModifiers {
    pub const NONE: Self = KeyModifiers(0);
    pub const CONTROL: Self = KeyModifiers(1);

    pub fn contains(self, other: Self) -> bool {
        self.0 & other.0 == other.0
    }
}

#[cfg(target_arch = "wasm32")]
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct KeyEvent {
    pub code: KeyCode,
    pub modifiers: KeyModifiers,
}

#[cfg(target_arch = "wasm32")]
impl KeyEvent {
    pub const fn new(code: KeyCode, modifiers: KeyModifiers) -> Self {
        KeyEvent { code, modifiers }
    }
}
