use std::cell::RefCell;

use crate::app::App;
use crate::keys::{KeyCode, KeyEvent, KeyModifiers};
use crate::ui::{self, Grid};

struct State {
    app: App,
    grid: Grid,
    width: usize,
    height: usize,
    frame: Vec<u8>,
}

thread_local! {
    static STATE: RefCell<Option<State>> = const { RefCell::new(None) };
}

impl State {
    fn redraw(&mut self) {
        self.grid = ui::build_grid(
            self.width,
            self.height,
            &self.app.game,
            self.app.message(),
            self.app.controls,
        );
        self.frame.clear();
        let _ = ui::render(&mut self.frame, &self.grid);
    }

    fn press(&mut self, key: KeyEvent) {
        if !crate::handle_key(&mut self.app, key) {
            self.redraw();
        }
    }
}

fn with_state(f: impl FnOnce(&mut State)) {
    STATE.with_borrow_mut(|state| {
        if let Some(state) = state {
            f(state);
        }
    });
}

#[no_mangle]
pub extern "C" fn wgt_layout_cols() -> usize {
    ui::REQ_HORIZ
}

#[no_mangle]
pub extern "C" fn wgt_layout_rows() -> usize {
    ui::REQ_VERT_SPACED
}

#[no_mangle]
pub extern "C" fn wgt_resize(width: usize, height: usize) {
    STATE.with_borrow_mut(|state| {
        let state = state.get_or_insert_with(|| {
            let app = App::new();
            let grid = ui::build_grid(0, 0, &app.game, None, app.controls);
            State {
                app,
                grid,
                width: 0,
                height: 0,
                frame: Vec::new(),
            }
        });
        state.width = width;
        state.height = height;
        state.redraw();
    });
}

#[no_mangle]
pub extern "C" fn wgt_key(code: u32) {
    let code = match code {
        8 => KeyCode::Backspace,
        13 => KeyCode::Enter,
        27 => KeyCode::Esc,
        _ => match char::from_u32(code) {
            Some(c) => KeyCode::Char(c),
            None => return,
        },
    };
    with_state(|state| state.press(KeyEvent::new(code, KeyModifiers::NONE)));
}

#[no_mangle]
pub extern "C" fn wgt_click(x: usize, y: usize) {
    with_state(|state| {
        if let Some(key) = state.grid.hit_test(x, y) {
            state.press(key);
        }
    });
}

#[no_mangle]
pub extern "C" fn wgt_frame_ptr() -> *const u8 {
    STATE.with_borrow(|state| {
        state
            .as_ref()
            .map_or(std::ptr::null(), |s| s.frame.as_ptr())
    })
}

#[no_mangle]
pub extern "C" fn wgt_frame_len() -> usize {
    STATE.with_borrow(|state| state.as_ref().map_or(0, |s| s.frame.len()))
}
